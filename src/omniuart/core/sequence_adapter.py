"""Adapter for parsing uart-message-sequence.schema.json test sequences into OmniUART ScriptSpec instances."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from omniuart.core.models import (
    ScriptConfig,
    ScriptMeta,
    ScriptSpec,
    ScriptStep,
    StepAssertion,
)

EXCLUDED_SEQUENCES = {"g460", "g460-smoke-test-sequence", "g460-smoke-test-sequence.json"}


def parse_kit_sequence(data: Dict[str, Any], source_name: Optional[str] = None) -> ScriptSpec:
    """Parse a uart-message-sequence.schema.json dictionary into an OmniUART ScriptSpec.
    
    Explicitly excludes G460 sequence files.
    """
    title = data.get("title") or data.get("name") or "Unnamed Sequence"
    description = data.get("description")
    interface_ref = data.get("interfaceRef", "unknown_protocol")

    # Guard: check if source or title or interfaceRef is G460
    check_str = f"{source_name or ''} {title} {interface_ref}".lower()
    if "g460" in check_str:
        raise ValueError("G460 sequence is explicitly excluded from processing")

    meta = ScriptMeta(
        name=title,
        protocol=interface_ref,
        description=description,
        author=data.get("author"),
    )

    on_failure = data.get("onSequenceFailure", "abort")
    abort_on_error = (on_failure == "abort")
    config = ScriptConfig(
        abort_on_error=abort_on_error,
        default_timeout_ms=1000,
        inter_step_delay_ms=0,
    )

    steps: List[ScriptStep] = []
    raw_steps = data.get("steps", [])

    for idx, step_data in enumerate(raw_steps):
        step_name = step_data.get("name", f"Step {idx + 1}")
        action = step_data.get("action", "send")
        
        delay_ms = step_data.get("delayBeforeMs")
        if delay_ms is None and "delayRangeBeforeMs" in step_data:
            rng = step_data["delayRangeBeforeMs"]
            delay_ms = rng.get("minMs", 0) if isinstance(rng, dict) else None

        if action == "waitOnly":
            steps.append(
                ScriptStep(
                    name=step_name,
                    command=None,
                    delay_ms=delay_ms or 100,
                    log=f"Wait for {delay_ms or 100} ms",
                )
            )
            continue

        cmd_name = step_data.get("message") or step_data.get("command")
        params_raw = step_data.get("fieldValues", {})
        params: Dict[str, Any] = {}
        for pk, pv in params_raw.items():
            if isinstance(pv, dict) and "fromVariable" in pv:
                var_name = pv["fromVariable"]
                var_val = data.get("variables", {}).get(var_name)
                params[pk] = var_val if var_val is not None else 0
            elif isinstance(pv, dict) and "random" in pv:
                params[pk] = pv["random"].get("min", 0)
            else:
                params[pk] = pv

        expect = step_data.get("expect", {})
        expect_response = None
        resp_msgs = expect.get("responseMessages", [])
        if resp_msgs:
            expect_response = resp_msgs[0]
        timeout_ms = expect.get("timeoutMs")

        assertions: List[StepAssertion] = []
        raw_assertions = expect.get("fieldAssertions", [])
        for fa in raw_assertions:
            field_name = fa.get("field", "")
            op = fa.get("operator", "equals")
            val = fa.get("value")
            if val is None and "min" in fa:
                val = fa["min"]
            assertions.append(
                StepAssertion(
                    field=field_name,
                    op=op,
                    value=val,
                )
            )

        steps.append(
            ScriptStep(
                name=step_name,
                command=cmd_name,
                params=params,
                expect_response=expect_response,
                timeout_ms=timeout_ms,
                delay_ms=delay_ms,
                assertions=assertions,
            )
        )

    return ScriptSpec(
        version="1.0.0",
        meta=meta,
        config=config,
        steps=steps,
    )


def load_kit_sequence(source: Union[str, Path, Dict[str, Any]]) -> ScriptSpec:
    """Load a script specification from file path or dictionary conforming to uart-message-sequence.schema.json."""
    if isinstance(source, dict):
        return parse_kit_sequence(source)
    path = Path(source)
    source_name = path.name
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    return parse_kit_sequence(data, source_name=source_name)
