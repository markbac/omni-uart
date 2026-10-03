"""Explicit command safety replaces the `dashboard` substring heuristic (#262)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from omniuart.cli import main as cli_main
from omniuart.core.background import BackgroundDevice, VIRTUAL_PORT, is_safe_poll_command
from omniuart.core.catalog import CatalogManager
from omniuart.core.kit_adapter import parse_kit_protocol
from omniuart.core.models import CommandSafety, CommandSpec, ProtocolSpec, ScriptSpec, load_protocol
from omniuart.core.runner import ScriptRunner, StepStatus
from omniuart.core.session import CommandBlockedError, DeviceSession
from omniuart.core.transport import VirtualTransport
from omniuart.ui.app import app

NAMES = ["set_target_temperature", "forget_pairing", "start_sweeping", "get_status", "read_config", "ping"]


def _protocol(commands: list, **extra) -> dict:
    return {
        "schema_version": "1.0.0",
        "metadata": {"name": "SafetyTest", "version": "1.0.0"},
        "serial_config": {"baudrate": 9600},
        "framing": {"type": "binary", "header": [170], "length": {"type": "uint8"}, "command_id": {"type": "uint8"}, "integrity": {"algorithm": "sum8"}},
        "commands": commands,
        **extra,
    }


def _cmd(name: str, idx: int, **kw) -> dict:
    return {"name": name, "id": idx, "response": {"id": 128 + idx, "fields": [{"name": "v", "type": "uint8"}]}, **kw}


def test_names_never_cause_a_dashboard_tag_or_read_only_safety(tmp_path: Path) -> None:
    path = tmp_path / "p.json"
    path.write_text(json.dumps(_protocol([_cmd(n, i + 1) for i, n in enumerate(NAMES)])), encoding="utf-8")
    spec = load_protocol(path)
    assert all("dashboard" not in c.tags for c in spec.commands)
    assert all(c.safety is CommandSafety.MUTATING for c in spec.commands)


def test_kit_adapter_does_not_guess_from_names() -> None:
    kit = {
        "title": "K",
        "version": "1",
        "physicalLayer": {"baudRate": 9600},
        "commands": [{"name": n, "fields": [{"name": "op", "type": "uint", "sizeBytes": 1, "constValue": i + 1, "role": "discriminator"}]} for i, n in enumerate(NAMES)],
    }
    spec = parse_kit_protocol(kit)
    assert all("dashboard" not in c.tags and not c.is_read_only for c in spec.commands)


def test_explicit_tags_and_safety_are_kept() -> None:
    spec = ProtocolSpec.model_validate(_protocol([_cmd("get_status", 1, tags=["dashboard"], safety="read_only")]))
    cmd = spec.commands[0]
    assert cmd.tags == ["dashboard"] and cmd.is_read_only and not cmd.needs_confirmation


@pytest.mark.parametrize(
    "safety, confirm",
    [("read_only", False), ("idempotent", False), ("mutating", True), ("destructive", True)],
)
def test_confirmation_is_needed_for_mutating_and_destructive_only(safety: str, confirm: bool) -> None:
    assert CommandSpec(name="x", id=1, safety=safety).needs_confirmation is confirm


def test_unknown_safety_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CommandSpec(name="x", id=1, safety="harmless")


def test_poll_requires_explicit_read_only_with_defaults_and_a_response() -> None:
    spec = load_protocol(next(Path("examples/protocols").glob("binary_sensor_node.yaml")))
    assert [c.name for c in spec.commands if is_safe_poll_command(c)] == ["ping", "get_readings"]
    tagged_but_mutating = CommandSpec(name="get_x", id=1, tags=["dashboard"], safety="mutating")
    assert not is_safe_poll_command(tagged_but_mutating)


# ------------------------------------------------------------------ read-only session
def _spec() -> ProtocolSpec:
    return CatalogManager().get_protocol("binary_sensor_node")


def test_read_only_session_blocks_non_read_only_commands_without_writing() -> None:
    spec = _spec()
    writes: list = []

    class Spy(VirtualTransport):
        async def write(self, data: bytes) -> int:
            writes.append(data)
            return await super().write(data)

    async def go():
        async with DeviceSession(spec, Spy(spec, latency_ms=0, jitter_ms=0), read_only=True) as session:
            ok = await session.send("ping")
            with pytest.raises(CommandBlockedError, match="set_sampling_rate is idempotent|'set_sampling_rate' is idempotent"):
                await session.send("set_sampling_rate", {"rate_hz": 5})
            return ok

    assert asyncio.run(go()).ok
    assert len(writes) == 1, "only the read_only ping may reach the transport"


def test_script_step_for_a_blocked_command_is_an_error() -> None:
    spec = _spec()
    script = ScriptSpec.model_validate(
        {"meta": {"name": "s", "protocol": "binary_sensor_node"}, "steps": [{"command": "set_sampling_rate", "params": {"rate_hz": 5}}]}
    )

    async def go():
        async with DeviceSession(spec, VirtualTransport(spec, latency_ms=0, jitter_ms=0), read_only=True) as session:
            return await ScriptRunner(script, session).run()

    result = asyncio.run(go())
    assert result.steps[0].status is StepStatus.ERROR and "blocked" in result.steps[0].message


# ------------------------------------------------------------------ CLI
def test_cli_read_only_refuses_a_mutating_command(capsys) -> None:
    assert cli_main(["send", "binary_sensor_node", "set_sampling_rate", "-p", "rate_hz=5", "--virtual", "--read-only"]) == 2
    assert "read-only mode" in capsys.readouterr().err
    assert cli_main(["send", "binary_sensor_node", "ping", "--virtual", "--read-only"]) == 0


def test_cli_destructive_command_needs_yes(tmp_path: Path, monkeypatch, capsys) -> None:
    proto = _protocol([_cmd("erase_flash", 1, safety="destructive")])
    (tmp_path / "protocols").mkdir()
    (tmp_path / "protocols" / "dangerous.json").write_text(json.dumps(proto), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert cli_main(["send", "dangerous", "erase_flash", "--virtual"]) == 2
    assert "destructive" in capsys.readouterr().err
    assert cli_main(["send", "dangerous", "erase_flash", "--dry-run"]) == 0
    assert cli_main(["send", "dangerous", "erase_flash", "--virtual", "--yes"]) in (0, 1)  # sent: the outcome is the device's


# ------------------------------------------------------------------ web API
@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/serial/disconnect")


def _connect(client, read_only=False):
    r = client.post("/api/serial/connect", json={"port": "virtual", "baudrate": 115200, "protocol": "binary_sensor_node", "read_only": read_only})
    assert r.status_code == 200
    return r.json()


def test_web_send_needs_confirmation_for_mutating_commands(client) -> None:
    proto = CatalogManager().get_protocol("binary_sensor_node")
    assert proto.get_command("ping").safety is CommandSafety.READ_ONLY
    _connect(client)
    assert client.post("/api/send/binary_sensor_node", json={"command": "ping"}).status_code == 200
    assert client.post("/api/send/binary_sensor_node", json={"command": "set_sampling_rate", "params": {"rate_hz": 5}}).status_code == 200  # idempotent


def test_web_mutating_command_returns_428_until_confirmed(client, tmp_path: Path, monkeypatch) -> None:
    proto = _protocol([_cmd("reboot", 1, safety="mutating")])
    (tmp_path / "protocols").mkdir()
    (tmp_path / "protocols" / "mut.json").write_text(json.dumps(proto), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    import omniuart.ui.routes as routes

    monkeypatch.setattr(routes, "catalog", CatalogManager())
    assert client.post("/api/serial/connect", json={"port": "virtual", "baudrate": 9600, "protocol": "mut"}).status_code == 200
    unconfirmed = client.post("/api/send/mut", json={"command": "reboot"})
    assert unconfirmed.status_code == 428 and "confirm" in unconfirmed.json()["detail"]
    assert client.post("/api/send/mut", json={"command": "reboot", "confirm": True}).status_code in (200, 502, 504)


def test_web_read_only_connection_refuses_with_403(client) -> None:
    state = _connect(client, read_only=True)
    assert state["connection"]["read_only"] is True
    assert client.post("/api/send/binary_sensor_node", json={"command": "ping"}).status_code == 200
    blocked = client.post("/api/send/binary_sensor_node", json={"command": "set_sampling_rate", "params": {"rate_hz": 5}, "confirm": True})
    assert blocked.status_code == 403 and "read-only" in blocked.json()["detail"]


def test_dashboard_auto_run_skips_dashboard_commands_that_are_not_read_only(client, tmp_path: Path, monkeypatch) -> None:
    proto = _protocol(
        [
            _cmd("get_status", 1, tags=["dashboard"], safety="read_only"),
            _cmd("start_sweeping", 2, tags=["dashboard"]),  # tagged by hand but never declared read-only
        ]
    )
    (tmp_path / "protocols").mkdir()
    (tmp_path / "protocols" / "dash.json").write_text(json.dumps(proto), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    import omniuart.ui.routes as routes

    monkeypatch.setattr(routes, "catalog", CatalogManager())
    assert client.post("/api/serial/connect", json={"port": "virtual", "baudrate": 9600, "protocol": "dash"}).status_code == 200
    data = client.get("/api/dashboard/auto-run/dash").json()["data"]
    assert data["get_status"]["status"] != "SKIPPED"
    assert data["start_sweeping"]["status"] == "SKIPPED" and "read_only" in data["start_sweeping"]["error"]


# ------------------------------------------------------------------ desktop controller
def test_background_device_read_only_blocks_commands_and_raw_bytes() -> None:
    spec = _spec()
    dev = BackgroundDevice()
    try:
        dev.connect(VIRTUAL_PORT, 115200, read_only=True).result(timeout=5)
        assert dev.read_only
        assert dev.send(spec, "ping").result(timeout=5).ok
        with pytest.raises(CommandBlockedError):
            dev.send(spec, "set_sampling_rate", {"rate_hz": 5}).result(timeout=5)
        with pytest.raises(CommandBlockedError):
            dev.send_raw(b"\x00", spec=spec).result(timeout=5)
        dev.disconnect().result(timeout=5)
        assert not dev.read_only
    finally:
        dev.close()
