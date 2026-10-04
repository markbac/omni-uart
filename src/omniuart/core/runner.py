"""Script execution engine shared by the CLI and (future) web and desktop clients.

A :class:`ScriptRunner` executes a :class:`ScriptSpec` against a :class:`DeviceSession`: ordered steps,
delays, log messages, command send/receive with timeouts, field assertions, variables and
abort-or-continue failure handling. It never fabricates a result; a step passes only when the device
actually did what the script asserted.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from omniuart.core.limits import get_limits
from omniuart.core.codec import CodecError
from omniuart.core.models import ScriptSpec, ScriptStep, StepAssertion
from omniuart.core.session import CommandBlockedError, DeviceSession, Exchange, ExchangeStatus

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_.]*)\}")

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INVALID = 2
EXIT_TRANSPORT = 3


class StepStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"  # the device did not behave as the script requires
    ERROR = "error"  # the script or transport is broken (bad parameters, unknown operator, link failure)
    SKIPPED = "skipped"  # not run because an earlier step failed and abort_on_error is set


class ScriptError(Exception):
    """The script itself is invalid (unknown variable, unsupported operator, step without an action)."""


@dataclass
class AssertionResult:
    field: str
    op: str
    expected: Any
    actual: Any
    passed: bool
    message: str = ""


@dataclass
class StepResult:
    index: int
    name: str
    status: StepStatus
    message: str = ""
    duration_ms: float = 0.0
    exchange: Optional[Exchange] = None
    assertions: List[AssertionResult] = field(default_factory=list)
    transport_error: bool = False


@dataclass
class ScriptResult:
    name: str
    steps: List[StepResult] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return bool(self.steps) and all(s.status is StepStatus.PASSED for s in self.steps)

    @property
    def exit_code(self) -> int:
        """0 all passed, 1 a step failed, 2 the script is invalid, 3 the transport failed."""
        if any(s.transport_error for s in self.steps):
            return EXIT_TRANSPORT
        if any(s.status is StepStatus.ERROR for s in self.steps):
            return EXIT_INVALID
        if any(s.status in (StepStatus.FAILED, StepStatus.SKIPPED) for s in self.steps):
            return EXIT_FAILED
        return EXIT_OK

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable report including every transmitted and received frame."""
        return {
            "name": self.name,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "variables": self.variables,
            "steps": [
                {
                    "index": s.index,
                    "name": s.name,
                    "status": s.status.value,
                    "message": s.message,
                    "duration_ms": round(s.duration_ms, 3),
                    "request": s.exchange.request.hex(" ") if s.exchange else None,
                    "response": s.exchange.response_bytes.hex(" ") if s.exchange and s.exchange.response_bytes else None,
                    "fields": s.exchange.fields if s.exchange else {},
                    "assertions": [
                        {"field": a.field, "op": a.op, "expected": a.expected, "actual": a.actual, "passed": a.passed, "message": a.message}
                        for a in s.assertions
                    ],
                }
                for s in self.steps
            ],
        }


_OPERATORS = {
    "==": "eq", "=": "eq", "eq": "eq", "equals": "eq", "equal": "eq",
    "!=": "ne", "ne": "ne", "notequals": "ne", "notequal": "ne",
    "<": "lt", "lt": "lt", "lessthan": "lt",
    "<=": "le", "le": "le", "lte": "le", "lessthanorequal": "le",
    ">": "gt", "gt": "gt", "greaterthan": "gt",
    ">=": "ge", "ge": "ge", "gte": "ge", "greaterthanorequal": "ge",
    "in": "in",
    "tolerance": "approx", "approx": "approx", "within": "approx",
}


def substitute(value: Any, variables: Dict[str, Any]) -> Any:
    """Replace ``${name}`` references. A value that is exactly one reference keeps the variable's type."""
    if isinstance(value, str):
        whole = _VAR.fullmatch(value)
        if whole:
            return _lookup(whole.group(1), variables)
        return _VAR.sub(lambda m: str(_lookup(m.group(1), variables)), value)
    if isinstance(value, dict):
        return {k: substitute(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [substitute(v, variables) for v in value]
    return value


def _lookup(name: str, variables: Dict[str, Any]) -> Any:
    if name not in variables:
        raise ScriptError(f"undefined variable '${{{name}}}'")
    return variables[name]


def evaluate_assertion(assertion: StepAssertion, fields: Dict[str, Any], variables: Dict[str, Any]) -> AssertionResult:
    """Check one assertion against decoded response fields."""
    op_key = re.sub(r"[\s_-]", "", assertion.op.lower())
    op = _OPERATORS.get(op_key)
    if op is None:
        raise ScriptError(f"unsupported assertion operator '{assertion.op}'")
    expected = substitute(assertion.value, variables)
    if assertion.field not in fields:
        return AssertionResult(assertion.field, assertion.op, expected, None, False, f"field '{assertion.field}' is not in the response")
    actual = fields[assertion.field]
    tolerance = assertion.tolerance
    try:
        if op == "approx" or (op == "eq" and tolerance is not None):
            if tolerance is None:
                raise ScriptError("the 'tolerance' operator needs a tolerance value")
            ok = abs(float(actual) - float(expected)) <= float(tolerance)
        elif op == "eq":
            ok = actual == expected
        elif op == "ne":
            ok = actual != expected
        elif op == "in":
            if not isinstance(expected, (list, tuple, set)):
                raise ScriptError("the 'in' operator needs a list value")
            ok = actual in expected
        else:
            a, e = float(actual), float(expected)
            ok = {"lt": a < e, "le": a <= e, "gt": a > e, "ge": a >= e}[op]
    except (TypeError, ValueError) as exc:
        return AssertionResult(assertion.field, assertion.op, expected, actual, False, f"cannot compare {actual!r} with {expected!r}: {exc}")
    message = "" if ok else f"{assertion.field}: expected {assertion.op} {expected!r}, got {actual!r}"
    return AssertionResult(assertion.field, assertion.op, expected, actual, ok, message)


class ScriptRunner:
    """Execute a script against a session."""

    def __init__(
        self,
        script: ScriptSpec,
        session: DeviceSession,
        variables: Optional[Dict[str, Any]] = None,
        on_step: Optional[Callable[[StepResult], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        max_duration_s: Optional[float] = None,
    ) -> None:
        self.max_duration_s = max_duration_s if max_duration_s is not None else get_limits().script_duration_s
        self.script = script
        self.session = session
        self.variables: Dict[str, Any] = {**script.variables, **(variables or {})}
        self.on_step = on_step
        self.on_log = on_log

    def _timeout_for(self, step: ScriptStep) -> Optional[int]:
        """Step override, else an explicitly configured script default, else the command's own timeout."""
        if step.timeout_ms is not None:
            return step.timeout_ms
        if "default_timeout_ms" in self.script.config.model_fields_set:
            return self.script.config.default_timeout_ms
        return None

    async def run(self) -> ScriptResult:
        result = ScriptResult(name=self.script.meta.name)
        aborted = False
        steps = self.script.steps
        deadline = time.monotonic() + self.max_duration_s
        for index, step in enumerate(steps, 1):
            name = step.name or step.command or f"Step {index}"
            if not aborted and time.monotonic() > deadline:
                step_result = StepResult(index, name, StepStatus.ERROR, f"script exceeded its {self.max_duration_s:g} s duration limit")
                aborted = True
            elif aborted:
                step_result = StepResult(index, name, StepStatus.SKIPPED, "skipped after an earlier failure")
            else:
                if index > 1 and self.script.config.inter_step_delay_ms:
                    await asyncio.sleep(self.script.config.inter_step_delay_ms / 1000.0)
                started = time.monotonic()
                step_result = await self._run_step(index, name, step)
                step_result.duration_ms = (time.monotonic() - started) * 1000.0
                if step_result.status in (StepStatus.FAILED, StepStatus.ERROR) and self.script.config.abort_on_error:
                    aborted = True
            result.steps.append(step_result)
            if self.on_step:
                self.on_step(step_result)
        result.variables = dict(self.variables)
        return result

    async def _run_step(self, index: int, name: str, step: ScriptStep) -> StepResult:
        if not (step.command or step.delay_ms or step.log):
            return StepResult(index, name, StepStatus.ERROR, "step has no command, delay_ms or log (unsupported step type?)")
        try:
            if step.delay_ms:
                await asyncio.sleep(step.delay_ms / 1000.0)
            if step.log:
                message = str(substitute(step.log, self.variables))
                if self.on_log:
                    self.on_log(message)
            if not step.command:
                delay_msg = f"waited {step.delay_ms} ms" if step.delay_ms is not None else "completed step"
                return StepResult(index, name, StepStatus.PASSED, message if step.log else delay_msg)
            return await self._run_command(index, name, step)
        except ScriptError as exc:
            return StepResult(index, name, StepStatus.ERROR, str(exc))
        except CommandBlockedError as exc:
            return StepResult(index, name, StepStatus.ERROR, f"blocked: {exc}")
        except CodecError as exc:
            return StepResult(index, name, StepStatus.ERROR, f"invalid parameters: {exc}")

    async def _run_command(self, index: int, name: str, step: ScriptStep) -> StepResult:
        assert step.command
        cmd = self.session.resolve(step.command)
        if step.expect_response and cmd.response is None:
            raise ScriptError(f"step expects a response but command '{cmd.name}' defines none")
        params = substitute(step.params, self.variables)
        exchange = await self.session.send(cmd, params, timeout_ms=self._timeout_for(step))
        if exchange.status is ExchangeStatus.TRANSPORT_ERROR:
            return StepResult(index, name, StepStatus.ERROR, exchange.error or "transport error", exchange=exchange, transport_error=True)
        if not exchange.ok:
            return StepResult(index, name, StepStatus.FAILED, exchange.error or exchange.status.value, exchange=exchange)

        results = [evaluate_assertion(a, exchange.fields, self.variables) for a in step.assertions]
        if step.assertions and exchange.response is None:
            return StepResult(index, name, StepStatus.FAILED, "no response to assert on", exchange=exchange)
        failed = [r for r in results if not r.passed]
        if failed:
            return StepResult(index, name, StepStatus.FAILED, "; ".join(r.message for r in failed), exchange=exchange, assertions=results)
        for var, field_name in step.save.items():
            if field_name not in exchange.fields:
                return StepResult(index, name, StepStatus.FAILED, f"cannot save '{var}': field '{field_name}' is not in the response", exchange=exchange, assertions=results)
            self.variables[var] = exchange.fields[field_name]
        return StepResult(index, name, StepStatus.PASSED, "", exchange=exchange, assertions=results)
