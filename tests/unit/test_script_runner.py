"""The script runner really executes steps against a device (#193)."""

import json

import pytest

from omniuart.cli import main as cli_main
from omniuart.core.models import load_protocol, load_script
from omniuart.core.recorder import SessionRecorder
from omniuart.core.runner import (
    ScriptError,
    ScriptRunner,
    StepStatus,
    evaluate_assertion,
    substitute,
)
from omniuart.core.models import StepAssertion
from omniuart.core.session import DeviceSession
from omniuart.core.simulator import BaseDeviceSimulator
from omniuart.core.transport import VirtualSerialPair

PROTOCOL = """
schema_version: "1.0.0"
metadata: {name: Dev, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing:
  type: binary
  header: [0xAA, 0x55]
  length: {type: uint8}
  command_id: {type: uint8}
  integrity: {algorithm: crc16_modbus}
commands:
  - name: set
    id: 1
    parameters: [{name: value, type: uint16, min: 0, max: 1000}]
    response: {id: 0x81, timeout_ms: 200, fields: [{name: status, type: uint8}]}
  - name: get
    id: 2
    response: {id: 0x82, timeout_ms: 200, fields: [{name: value, type: uint16}, {name: temp, type: float32}]}
  - name: fire
    id: 3
"""


def script(steps, **config):
    return load_script(json.dumps({"version": "1.0.0", "meta": {"name": "t", "protocol": "dev"}, "config": config, "steps": steps}))


class Device(BaseDeviceSimulator):
    """Remembers the value written with `set` and reports it with `get`."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.value = 0

    def handle_command(self, cmd, params):
        if cmd.name == "set":
            self.value = params["value"]
            return {"status": 0}
        if cmd.name == "get":
            return {"value": self.value, "temp": 21.5}
        return {}


@pytest.fixture()
async def rig():
    spec = load_protocol(PROTOCOL)
    pair = VirtualSerialPair()
    await pair.open()
    device = Device(spec=spec, transport=pair.device, latency_ms=0)
    await device.start()
    session = DeviceSession(spec, pair.host, recorder=SessionRecorder())
    await session.open()
    yield session, device
    await device.stop()
    await pair.close()


@pytest.mark.asyncio
async def test_steps_run_in_order_and_assertions_see_real_responses(rig):
    session, device = rig
    s = script([
        {"command": "set", "params": {"value": 42}, "assertions": [{"field": "status", "op": "==", "value": 0}]},
        {"command": "get", "assertions": [{"field": "value", "op": "==", "value": 42}, {"field": "temp", "op": "==", "value": 21.5, "tolerance": 0.01}]},
    ])
    result = await ScriptRunner(s, session).run()
    assert result.passed and result.exit_code == 0
    assert device.value == 42
    assert [e.direction for e in session.recorder.events] == ["tx", "rx", "tx", "rx"]


@pytest.mark.asyncio
async def test_failed_assertion_fails_and_aborts_by_default(rig):
    session, _ = rig
    s = script([
        {"command": "get", "assertions": [{"field": "value", "op": ">", "value": 100}]},
        {"command": "fire"},
    ])
    result = await ScriptRunner(s, session).run()
    assert [r.status for r in result.steps] == [StepStatus.FAILED, StepStatus.SKIPPED]
    assert "expected > 100" in result.steps[0].message
    assert result.exit_code == 1 and not result.passed


@pytest.mark.asyncio
async def test_abort_on_error_false_continues(rig):
    session, _ = rig
    s = script([
        {"command": "get", "assertions": [{"field": "value", "op": ">", "value": 100}]},
        {"command": "fire"},
    ], abort_on_error=False)
    result = await ScriptRunner(s, session).run()
    assert [r.status for r in result.steps] == [StepStatus.FAILED, StepStatus.PASSED]
    assert result.exit_code == 1


@pytest.mark.asyncio
async def test_variables_saved_from_responses_feed_later_steps(rig):
    session, device = rig
    s = script([
        {"command": "set", "params": {"value": 7}},
        {"command": "get", "save": {"previous": "value"}},
        {"command": "set", "params": {"value": "${previous}"}},
        {"command": "get", "assertions": [{"field": "value", "op": "==", "value": "${previous}"}]},
        {"log": "value is ${previous}"},
    ])
    logs = []
    result = await ScriptRunner(s, session, on_log=logs.append).run()
    assert result.passed, [r.message for r in result.steps]
    assert result.variables["previous"] == 7 and logs == ["value is 7"]


@pytest.mark.asyncio
async def test_initial_variables_come_from_script_and_caller(rig):
    session, device = rig
    s = load_script(json.dumps({"meta": {"name": "t", "protocol": "dev"}, "variables": {"v": 3, "w": 4},
                                "steps": [{"command": "set", "params": {"value": "${v}"}}]}))
    await ScriptRunner(s, session, variables={"v": 9}).run()
    assert device.value == 9


@pytest.mark.asyncio
async def test_timeout_is_a_failed_step(rig):
    session, device = rig
    await device.stop()  # nobody answers
    result = await ScriptRunner(script([{"command": "get", "timeout_ms": 60}]), session).run()
    assert result.steps[0].status is StepStatus.FAILED and "no response" in result.steps[0].message


@pytest.mark.asyncio
async def test_invalid_parameters_and_unknown_variables_are_errors(rig):
    session, _ = rig
    bad_range = await ScriptRunner(script([{"command": "set", "params": {"value": 5000}}]), session).run()
    assert bad_range.steps[0].status is StepStatus.ERROR and bad_range.exit_code == 2
    unknown_var = await ScriptRunner(script([{"command": "set", "params": {"value": "${nope}"}}]), session).run()
    assert unknown_var.steps[0].status is StepStatus.ERROR and "undefined variable" in unknown_var.steps[0].message


@pytest.mark.asyncio
async def test_unsupported_step_type_is_not_silently_passed(rig):
    session, _ = rig
    result = await ScriptRunner(script([{"repeat": 3, "steps": []}]), session).run()
    assert result.steps[0].status is StepStatus.ERROR


@pytest.mark.asyncio
async def test_missing_response_field_and_missing_save_field_fail(rig):
    session, _ = rig
    r1 = await ScriptRunner(script([{"command": "get", "assertions": [{"field": "nope", "op": "==", "value": 1}]}]), session).run()
    assert r1.steps[0].status is StepStatus.FAILED and "not in the response" in r1.steps[0].message
    r2 = await ScriptRunner(script([{"command": "get", "save": {"x": "nope"}}]), session).run()
    assert r2.steps[0].status is StepStatus.FAILED


@pytest.mark.asyncio
async def test_expect_response_on_a_command_without_one_is_a_script_error(rig):
    session, _ = rig
    result = await ScriptRunner(script([{"command": "fire", "expect_response": "fire_reply"}]), session).run()
    assert result.steps[0].status is StepStatus.ERROR


@pytest.mark.asyncio
async def test_delay_and_inter_step_delay_are_honoured(rig):
    import time

    session, _ = rig
    started = time.monotonic()
    await ScriptRunner(script([{"delay_ms": 120}, {"command": "fire"}, {"command": "fire"}], inter_step_delay_ms=50), session).run()
    assert time.monotonic() - started >= 0.12 + 0.1 - 0.02


@pytest.mark.asyncio
async def test_transport_failure_maps_to_exit_code_3(rig):
    session, _ = rig
    await session.transport.close()  # link goes away mid-script
    result = await ScriptRunner(script([{"command": "get"}]), session).run()
    assert result.exit_code == 3


def test_operators_and_aliases():
    def check(op, actual, expected, tol=None):
        return evaluate_assertion(StepAssertion(field="f", op=op, value=expected, tolerance=tol), {"f": actual}, {}).passed

    assert check("==", 1, 1) and not check("==", 1, 2)
    assert check("equals", 1, 1) and check("!=", 1, 2) and check("notEquals", 1, 2)
    assert check("<", 1, 2) and check("<=", 2, 2) and check(">", 3, 2) and check(">=", 2, 2)
    assert check("in", 2, [1, 2]) and not check("in", 3, [1, 2])
    assert check("tolerance", 3.31, 3.3, 0.05) and not check("tolerance", 3.5, 3.3, 0.05)
    assert check("==", 3.31, 3.3, 0.05)
    assert not check("<", "abc", 5)  # uncomparable is a failure, not a pass
    with pytest.raises(ScriptError):
        check("~=", 1, 1)
    with pytest.raises(ScriptError):
        check("tolerance", 1, 1)


def test_substitute_keeps_types_for_whole_values():
    assert substitute("${a}", {"a": 5}) == 5
    assert substitute("x${a}y", {"a": 5}) == "x5y"
    assert substitute({"k": ["${a}"]}, {"a": 1}) == {"k": [1]}


# ----------------------------------------------------------------- CLI
def test_cli_run_executes_the_example_against_the_virtual_device(capsys, tmp_path):
    record, report = tmp_path / "s.jsonl", tmp_path / "r.json"
    code = cli_main(["run", "examples/scripts/sensor_test_suite.yaml", "--virtual", "--record", str(record), "--report", str(report)])
    out = capsys.readouterr().out
    assert code == 0 and "Result: PASSED" in out
    events = [json.loads(line) for line in record.read_text().splitlines()]
    assert [e["direction"] for e in events] == ["tx", "rx"] * 3
    data = json.loads(report.read_text())
    assert data["passed"] and data["steps"][1]["fields"]["channel"] == 0


def test_cli_run_failure_exit_code_and_skipped_steps(capsys):
    code = cli_main(["run", "examples/scripts/actuator_calibration.json", "--virtual"])
    out = capsys.readouterr().out
    assert code == 1 and "[FAIL]" in out and "[SKIP]" in out


def test_cli_run_requires_a_transport(capsys):
    assert cli_main(["run", "examples/scripts/sensor_test_suite.yaml"]) == 2
    assert "--virtual" in capsys.readouterr().err


def test_cli_run_unknown_script(capsys):
    assert cli_main(["run", "no-such-script", "--virtual"]) == 1


def test_loaders_accept_long_inline_documents():
    long_desc = "x" * 400
    spec = load_protocol(PROTOCOL.replace("name: Dev", f"name: Dev, description: {long_desc}"))
    assert spec.metadata.description == long_desc
