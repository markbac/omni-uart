"""The device dashboard is driven by real exchanges: live state, traffic and transfers (#230, #246, #318)."""

from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from omniuart.core.catalog import CatalogManager
from omniuart.core.device_ui import TransferProtocolSpec
from omniuart.core.models import load_protocol
from omniuart.core.session import DeviceSession
from omniuart.core.transfer import TransferState
from omniuart.core.transfer_session import SessionTransfer, TransferDefinitionError
from omniuart.core.transport import VirtualTransport
from omniuart.ui.app import app

FLASH_PROTOCOL = """\
schema_version: "1.0.0"
metadata: {name: "FlashNode", version: "1.0.0"}
serial_config: {baudrate: 115200}
framing:
  type: binary
  header: [0xAA, 0x55]
  length: {type: uint16, endian: little, includes: payload_only}
  command_id: {type: uint8}
  integrity: {algorithm: crc16_modbus}
commands:
  - name: get_version
    id: 0x01
    safety: read_only
    response: {id: 0x81, timeout_ms: 100, fields: [{name: fw_version, type: uint16}]}
  - name: xfer_start
    id: 0x10
    safety: mutating
    parameters: [{name: total_size, type: uint32}]
    response: {id: 0x90, timeout_ms: 100, fields: [{name: accepted, type: uint8}]}
  - name: xfer_data
    id: 0x11
    safety: mutating
    parameters: [{name: sequence, type: uint16}, {name: data, type: bytes}]
    response: {id: 0x91, timeout_ms: 100, fields: [{name: ack_seq, type: uint16}]}
  - name: xfer_commit
    id: 0x12
    safety: destructive
    response: {id: 0x92, timeout_ms: 100, fields: [{name: ok, type: uint8}]}
"""

FLASH_UI = """\
identity: {name: "Flash Node"}
protocol_ref: FlashNode
transfer_protocol: {start_command: xfer_start, chunk_command: xfer_data, commit_command: xfer_commit, default_chunk_size: 64}
panels:
  - name: main
    title: Main
    groups:
      - name: fw
        title: Firmware
        widgets:
          - {widget_type: firmware_update, field_ref: firmware, label: Flash firmware, supported_file_types: [".bin"], destructive: true}
"""


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/serial/disconnect")


@pytest.fixture()
def flash_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "protocols").mkdir()
    (tmp_path / "protocols" / "flash_node.yaml").write_text(FLASH_PROTOCOL, encoding="utf-8")
    (tmp_path / ".omniuart" / "ui").mkdir(parents=True)
    (tmp_path / ".omniuart" / "ui" / "flash_node_ui.yaml").write_text(FLASH_UI, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    import omniuart.ui.routes as routes

    monkeypatch.setattr(routes, "catalog", CatalogManager(protocol_dirs=[tmp_path / "protocols"]))
    return tmp_path


def _connect(client: TestClient, protocol: str, read_only: bool = False) -> None:
    body = {"port": "virtual", "protocol": protocol, "read_only": read_only}
    assert client.post("/api/serial/connect", json=body).status_code == 200


def test_dashboard_page_uses_the_bundled_ui_definition(client: TestClient) -> None:
    page = client.get("/dashboard/binary_sensor_node")
    assert page.status_code == 200
    assert "Environmental Sensor Node" in page.text
    assert 'data-command="set_sampling_rate"' in page.text and 'data-param="rate_hz"' in page.text
    assert client.get("/dashboard/no_such_protocol").status_code == 404


def test_state_comes_only_from_real_exchanges_and_goes_offline_on_disconnect(client: TestClient) -> None:
    state = client.get("/api/device/binary_sensor_node/state").json()
    assert state["connection"]["connected"] is False
    assert client.post("/api/device/binary_sensor_node/refresh").status_code == 409  # nothing to read from

    _connect(client, "binary_sensor_node")
    refreshed = client.post("/api/device/binary_sensor_node/refresh").json()
    assert refreshed["polled"]["get_readings"] == "ok"
    fields = refreshed["state"]["fields"]
    assert fields["get_readings.temperature"]["quality"] == "good"
    assert refreshed["exchanges"] and refreshed["exchanges"][0]["crc_valid"] is True

    sent = client.post("/api/send/binary_sensor_node", json={"command": "ping"}).json()
    newest = client.get("/api/device/binary_sensor_node/state").json()["exchanges"][0]
    assert newest["exchange_id"] == sent["exchange_id"] and newest["command_name"] == "ping"

    client.post("/api/serial/disconnect")
    fields = client.get("/api/device/binary_sensor_node/state").json()["state"]["fields"]
    assert {v["quality"] for v in fields.values()} == {"offline"}


def _transfer(client: TestClient, confirm: bool = True, name: str = "fw.bin", data: bytes = bytes(range(200))):
    body = {"widget_ref": "firmware", "file_name": name, "data_base64": base64.b64encode(data).decode(), "confirm": confirm}
    return client.post("/api/device/flash_node/transfer", json=body)


def test_transfer_runs_over_the_link_and_reports_the_device_commit(client: TestClient, flash_dir: Path) -> None:
    _connect(client, "flash_node")
    assert _transfer(client, confirm=False).status_code == 428
    assert _transfer(client, name="fw.txt").status_code == 422  # not a supported file type
    started = _transfer(client)
    assert started.status_code == 200
    job_id = started.json()["job_id"]
    for _ in range(100):
        job = client.get(f"/api/device/flash_node/transfer/{job_id}").json()
        if job["done"]:
            break
        time.sleep(0.05)
    assert job["state"] == "completed" and job["committed"] is True
    assert job["progress"]["total_chunks"] == 4 and job["progress"]["percent_complete"] == 100.0


def test_transfer_is_refused_on_a_read_only_link(client: TestClient, flash_dir: Path) -> None:
    _connect(client, "flash_node", read_only=True)
    assert _transfer(client).status_code == 403


def test_transfer_needs_a_transfer_definition(client: TestClient) -> None:
    _connect(client, "binary_sensor_node")
    body = {"widget_ref": "anything", "file_name": "a.bin", "data_base64": "AA==", "confirm": True}
    assert client.post("/api/device/binary_sensor_node/transfer", json=body).status_code == 404


def _flash_spec(tmp_path: Path):
    path = tmp_path / "flash_node.yaml"
    path.write_text(FLASH_PROTOCOL, encoding="utf-8")
    return load_protocol(path)


def _upload(spec, definition, transport):
    async def go():
        async with DeviceSession(spec, transport) as session:
            return await SessionTransfer(spec, definition).upload(session, "fw.bin", bytes(150))

    return asyncio.run(go())


def test_session_transfer_is_not_committed_without_a_commit_command(tmp_path: Path) -> None:
    spec = _flash_spec(tmp_path)
    outcome = _upload(spec, TransferProtocolSpec(chunk_command="xfer_data", default_chunk_size=64), VirtualTransport(spec, latency_ms=0.1, jitter_ms=0))
    assert outcome.state is TransferState.COMPLETED and outcome.committed is False


def test_session_transfer_fails_when_the_device_rejects_the_commit_or_never_acks(tmp_path: Path) -> None:
    spec = _flash_spec(tmp_path)
    definition = TransferProtocolSpec(chunk_command="xfer_data", commit_command="xfer_commit", default_chunk_size=64, retries=1)

    rejecting = VirtualTransport(spec, latency_ms=0.1, jitter_ms=0)
    rejecting.register_response(0x12, b"\x00\x01\x02")  # garbage instead of a commit confirmation
    outcome = _upload(spec, definition, rejecting)
    assert outcome.state is TransferState.FAILED and outcome.committed is False and "commit" in (outcome.error or "")

    silent = VirtualTransport(spec, latency_ms=0.1, jitter_ms=0)
    silent.register_response(0x11, b"")  # chunks are never acknowledged
    outcome = _upload(spec, definition, silent)
    assert outcome.state is TransferState.FAILED and outcome.progress.retries_count == 2


def test_transfer_definition_must_match_the_protocol(tmp_path: Path) -> None:
    spec = _flash_spec(tmp_path)
    with pytest.raises(TransferDefinitionError):
        SessionTransfer(spec, TransferProtocolSpec(chunk_command="no_such_command"))
    with pytest.raises(TransferDefinitionError):
        SessionTransfer(spec, TransferProtocolSpec(chunk_command="get_version"))  # no data parameter
