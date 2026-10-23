"""Tests for all P3 issue fixes (#335, #333, #339, #326, #322, #337, #338, #340, #252)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from omniuart.core.asyncapi_exporter import export_asyncapi_dict
from omniuart.core.catalog import CatalogManager
from omniuart.core.kit_adapter import parse_kit_protocol
from omniuart.core.models import (
    CommandSafety,
    CommandSpec,
    FieldSpec,
    FieldType,
    FramingConfig,
    FramingType,
    ProtocolMeta,
    ProtocolSpec,
    SerialConfig,
)
from omniuart.core.recorder import SessionRecorder
from omniuart.core.session import DeviceSession
from omniuart.core.transport import VirtualTransport
from omniuart.ui.connection import ConnectionManager, VIRTUAL_PORT


# ---------------------------------------------------------------------------
# Issue #335: Kit adapter command safety derivation
# ---------------------------------------------------------------------------
def test_kit_adapter_command_safety_inference():
    kit_data = {
        "title": "SafetyTestProto",
        "version": "1.0.0",
        "physicalLayer": {"baudRate": 115200},
        "commands": [
            {"name": "get_telemetry", "fields": []},
            {"name": "read_registers", "fields": []},
            {"name": "poll_status", "fields": []},
            {"name": "reset_device", "fields": []},
            {"name": "erase_flash", "fields": []},
            {"name": "set_timeout", "fields": []},
            {"name": "custom_read", "readOnly": True, "fields": []},
            {"name": "custom_idempotent", "idempotent": True, "fields": []},
            {"name": "tagged_danger", "tags": ["destructive"], "fields": []},
            {"name": "tagged_monitor", "tags": ["telemetry"], "fields": []},
            {"name": "unknown_action", "fields": []},
        ],
    }

    spec = parse_kit_protocol(kit_data)

    cmd_map = {c.name: c for c in spec.commands}

    assert cmd_map["get_telemetry"].safety == CommandSafety.READ_ONLY
    assert "read-only" in str(cmd_map["get_telemetry"].safety_reason).lower()

    assert cmd_map["read_registers"].safety == CommandSafety.READ_ONLY
    assert cmd_map["poll_status"].safety == CommandSafety.READ_ONLY

    assert cmd_map["reset_device"].safety == CommandSafety.DESTRUCTIVE
    assert "destructive" in str(cmd_map["reset_device"].safety_reason).lower()
    assert cmd_map["erase_flash"].safety == CommandSafety.DESTRUCTIVE

    assert cmd_map["set_timeout"].safety == CommandSafety.IDEMPOTENT

    assert cmd_map["custom_read"].safety == CommandSafety.READ_ONLY
    assert "readonly: true" in str(cmd_map["custom_read"].safety_reason).lower()

    assert cmd_map["custom_idempotent"].safety == CommandSafety.IDEMPOTENT

    assert cmd_map["tagged_danger"].safety == CommandSafety.DESTRUCTIVE
    assert cmd_map["tagged_monitor"].safety == CommandSafety.READ_ONLY

    # Unknown defaults to mutating with reason
    assert cmd_map["unknown_action"].safety == CommandSafety.MUTATING
    assert "defaulted to mutating" in str(cmd_map["unknown_action"].safety_reason).lower()


# ---------------------------------------------------------------------------
# Issue #333: Session recorder add_transaction wired to session.send
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_session_records_completed_transactions(tmp_path: Path):
    spec = ProtocolSpec(
        schema_version="1.0.0",
        metadata=ProtocolMeta(name="TxTest", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY, header=[0xAA]),
        commands=[
            CommandSpec(
                name="ping",
                id=1,
                safety=CommandSafety.READ_ONLY,
                parameters=[],
                response=None,
            )
        ],
    )

    recorder = SessionRecorder(protocol_name=spec.metadata.name)
    transport = VirtualTransport(spec, latency_ms=1.0)
    session = DeviceSession(spec, transport, recorder=recorder)

    await session.open()
    try:
        exchange = await session.send("ping")
        assert exchange.ok is True
    finally:
        await session.close()

    # Verify transaction was recorded
    assert len(recorder.transactions) == 1
    tx = recorder.transactions[0]
    assert tx.command_name == "ping"
    assert tx.command_id == 1
    assert tx.status == "ok"
    assert tx.tx_event is not None
    assert tx.tx_event.command_name == "ping"

    # Export to jsonl
    jsonl_file = tmp_path / "test.jsonl"
    recorder.export_jsonl(jsonl_file)
    assert jsonl_file.exists()
    lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1

    # Export to pcapng
    pcapng_file = tmp_path / "test.pcapng"
    recorder.export_pcapng(pcapng_file)
    assert pcapng_file.exists()
    assert pcapng_file.stat().st_size > 0


# ---------------------------------------------------------------------------
# Issue #339: Catalog error reporting & ignore pattern matching
# ---------------------------------------------------------------------------
def test_catalog_error_tracking_and_ignore_patterns(tmp_path: Path):
    # Create valid and invalid protocol files
    valid_proto = tmp_path / "latest_sensor.yaml"
    valid_proto.write_text(
        """schema_version: "1.0.0"
metadata: {name: LatestSensor, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing: {type: binary}
commands: []
""",
        encoding="utf-8",
    )

    invalid_proto = tmp_path / "broken_proto.yaml"
    invalid_proto.write_text("invalid: yaml: [broken syntax", encoding="utf-8")

    # Catalog with ignored_pattern = ['test']
    # 'test' must NOT ignore 'latest_sensor.yaml'
    catalog = CatalogManager(protocol_dirs=[tmp_path], ignored_patterns=["test"])

    files = catalog.list_protocol_files()
    file_names = [f.name for f in files]
    assert "latest_sensor.yaml" in file_names
    assert "broken_proto.yaml" in file_names

    # Loading broken_proto must raise ValueError with clear error message, not return None
    with pytest.raises(ValueError, match="failed to load"):
        catalog.get_protocol("broken_proto.yaml")

    # Error is preserved in catalog
    assert catalog.get_load_error("broken_proto.yaml") is not None

    # Summary reports the failure
    summary = catalog.catalog_summary()
    assert len(summary["errors"]) >= 1
    assert any(err["filename"] == "broken_proto.yaml" for err in summary["errors"])

    # Valid protocol loads properly
    valid_spec = catalog.get_protocol("latest_sensor.yaml")
    assert valid_spec is not None
    assert valid_spec.metadata.name == "LatestSensor"


# ---------------------------------------------------------------------------
# Issue #326: ConnectionManager locks connect and disconnect
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_connection_manager_connect_disconnect_locking():
    cm = ConnectionManager()
    await cm.connect(VIRTUAL_PORT, 115200, True, True)
    assert cm.connected is True

    spec = ProtocolSpec(
        schema_version="1.0.0",
        metadata=ProtocolMeta(name="LockTest", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY),
        commands=[],
    )

    request_started = asyncio.Event()
    request_finish = asyncio.Event()
    in_flight_completed = False

    async def in_flight_request():
        nonlocal in_flight_completed
        async with cm.use(spec) as _:
            request_started.set()
            # Simulate active request holding lock
            await request_finish.wait()
            in_flight_completed = True

    # Start in-flight request task
    task = asyncio.create_task(in_flight_request())
    await request_started.wait()

    # Concurrently issue disconnect
    disconnect_task = asyncio.create_task(cm.disconnect())

    # Disconnect must be waiting for lock, request should not be terminated prematurely
    await asyncio.sleep(0.02)
    assert not disconnect_task.done()

    # Finish in-flight request
    request_finish.set()
    await task
    assert in_flight_completed is True

    # Disconnect should now finish cleanly
    await disconnect_task
    assert cm.connected is False


# ---------------------------------------------------------------------------
# Issue #337: AsyncAPI export bytes as hex pattern and x-unit
# ---------------------------------------------------------------------------
def test_asyncapi_hex_and_x_unit():
    spec = ProtocolSpec(
        schema_version="1.0.0",
        metadata=ProtocolMeta(name="HexProto", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY),
        commands=[
            CommandSpec(
                name="set_data",
                id=1,
                parameters=[
                    FieldSpec(name="raw_buf", type=FieldType.BYTES, length=8),
                    FieldSpec(name="temp", type=FieldType.FLOAT32, unit="degC", scale=0.1),
                ],
            )
        ],
    )

    doc = export_asyncapi_dict(spec)
    schemas = doc["components"]["schemas"]
    payload_schema = schemas["set_data_Request"]["properties"]

    raw_buf_schema = payload_schema["raw_buf"]
    assert raw_buf_schema["type"] == "string"
    assert "pattern" in raw_buf_schema
    assert "contentEncoding" not in raw_buf_schema

    temp_schema = payload_schema["temp"]
    assert temp_schema.get("x-unit") == "degC"
    assert "unit" not in temp_schema
    assert "multipleOf" not in temp_schema
    assert temp_schema.get("x-scale") == 0.1


def test_docs_all_markdown_writes_one_file_per_protocol(tmp_path, capsys) -> None:
    """#322: `docs --all --format markdown` writes Markdown for every protocol, not the HTML site."""
    from omniuart.cli import main
    from omniuart.core.catalog import CatalogManager

    assert main(["docs", "--all", "--format", "markdown", "--output-dir", str(tmp_path)]) == 0
    written = sorted(p.stem for p in tmp_path.glob("*.md"))
    assert written == sorted(p.stem for p in CatalogManager().list_protocol_files())
    assert not list(tmp_path.glob("*.html"))
