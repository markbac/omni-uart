import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import FrameCodec, decode_fields, encode_fields, FieldSpec, FieldType
from omniuart.core.dissector import dissect_frame
from omniuart.core.kit_adapter import parse_kit_protocol
from omniuart.core.models import (
    CommandSafety,
    CommandSpec,
    FramingConfig,
    FramingType,
    IntegritySpec,
    ProtocolMeta,
    ProtocolSpec,
    ResponseSpec,
    SerialConfig,
)
from omniuart.core.replayer import SessionReplayer, ReplayTimingMode, ReplayResult
from omniuart.core.runner import StepAssertion, evaluate_assertion
from omniuart.core.session import SerialSession, ExchangeStatus
from omniuart.core.simulator import ATModemSimulator, ModbusRtuSimulator
from omniuart.core.transport import VirtualTransport
from omniuart.generators import generate_c_header, generate_python_dataclasses
from omniuart.importers_exporters import export_csv_protocol, import_csv_protocol


# ---------------------------------------------------------------------------
# 1. Issue #328: Kit adapter flowControl
# ---------------------------------------------------------------------------
def test_kit_adapter_flow_control():
    kit_data = {
        "title": "HCI Test",
        "version": "1.0.0",
        "physicalLayer": {
            "baudRate": 115200,
            "dataBits": 8,
            "parity": "none",
            "stopBits": 1,
            "flowControl": "rts-cts",
        },
        "framing": {"style": "binary"},
        "commands": [],
    }
    spec = parse_kit_protocol(kit_data)
    assert spec.serial_config.flow_control == "hardware"

    # Converter should output flowControl: "rts-cts"
    # verify kit adapter also accepts backward compatible hardwareFlowControl
    kit_legacy = {
        "title": "Legacy",
        "version": "1.0.0",
        "physicalLayer": {
            "baudRate": 9600,
            "hardwareFlowControl": True,
        },
        "framing": {"style": "binary"},
        "commands": [],
    }
    spec_legacy = parse_kit_protocol(kit_legacy)
    assert spec_legacy.serial_config.flow_control == "hardware"


# ---------------------------------------------------------------------------
# 2. Issue #329: Dissector CRC calculated vs received
# ---------------------------------------------------------------------------
def test_dissector_crc_calculated_and_received():
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="CRCProto", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(
            type=FramingType.BINARY,
            header=[0xAA, 0x55],
            integrity=IntegritySpec(algorithm="crc16_modbus", endian="little"),
        ),
        commands=[
            CommandSpec(
                name="ping",
                id=1,
                safety=CommandSafety.READ_ONLY,
                parameters=[FieldSpec(name="data", type=FieldType.UINT8)],
            )
        ],
    )
    codec = FrameCodec(spec)
    # Ping with valid CRC
    valid_raw = codec.encode_command("ping", {"data": 42})
    dissected_valid = dissect_frame(spec, valid_raw)
    assert dissected_valid.valid is True
    assert dissected_valid.crc_info is not None
    assert dissected_valid.crc_info["valid"] is True
    assert dissected_valid.crc_info["calculated"] == dissected_valid.crc_info["received"]
    assert dissected_valid.crc_info["calculated"] != 0

    # Corrupt the CRC bytes at the end
    corrupted_raw = bytearray(valid_raw)
    corrupted_raw[-1] ^= 0xFF
    dissected_corrupt = dissect_frame(spec, bytes(corrupted_raw))
    assert dissected_corrupt.valid is False
    assert dissected_corrupt.crc_info is not None
    assert dissected_corrupt.crc_info["valid"] is False
    assert dissected_corrupt.crc_info["calculated"] != dissected_corrupt.crc_info["received"]

    diag_text = dissected_corrupt.format_diagnostic_text()
    assert "Calculated" in diag_text
    assert "Received" in diag_text


# ---------------------------------------------------------------------------
# 3. Issue #319: Code generators valid output
# ---------------------------------------------------------------------------
def test_code_generators_compile():
    catalog = CatalogManager()
    for proto_file in catalog.list_protocol_files():
        spec = catalog.get_protocol(proto_file.name)
        if spec is None:
            continue

        c_code = generate_c_header(spec)
        assert "command_id_t;" in c_code

        py_code = generate_python_dataclasses(spec)
        # compile python code to verify syntax
        compiled = compile(py_code, f"<dataclass_{spec.metadata.name}>", "exec")
        assert compiled is not None


# ---------------------------------------------------------------------------
# 4. Issue #320: CSV import/export baudrate, framing, and loss reporting
# ---------------------------------------------------------------------------
def test_csv_import_export_metadata_and_losses():
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="SpecialProto", version="2.0.0"),
        serial_config=SerialConfig(baudrate=921600),
        framing=FramingConfig(type=FramingType.DELIMITED, delimiter=";"),
        commands=[
            CommandSpec(
                name="status",
                id="GET_STATUS",
                safety=CommandSafety.READ_ONLY,
                response=ResponseSpec(fields=[FieldSpec(name="ok", type=FieldType.BOOL)]),
            )
        ],
    )
    export_losses: list[str] = []
    csv_text = export_csv_protocol(spec, losses=export_losses)
    assert "921600" in csv_text
    assert "delimited" in csv_text
    assert any("response definition" in loss_msg for loss_msg in export_losses)

    imported, import_losses = import_csv_protocol(csv_text)
    assert imported.serial_config.baudrate == 921600
    assert imported.framing.type == FramingType.DELIMITED
    assert len(import_losses) > 0


# ---------------------------------------------------------------------------
# 5. Issue #327: FieldSpec offset and expression
# ---------------------------------------------------------------------------
def test_field_spec_offset_and_expression():
    specs = [
        FieldSpec(name="header_id", type=FieldType.UINT8, offset=0),
        FieldSpec(name="payload_len", type=FieldType.UINT8, offset=2),
        FieldSpec(name="data", type=FieldType.UINT16, offset=4),
        FieldSpec(name="computed", type=FieldType.UINT16, expression="data * 2"),
    ]
    encoded = encode_fields(specs[:3], {"header_id": 1, "payload_len": 2, "data": 100})
    # Byte 0 = 1, Byte 1 = 0, Byte 2 = 2, Byte 3 = 0, Byte 4..5 = 100 (0x64, 0x00)
    assert len(encoded) >= 6
    assert encoded[0] == 1
    assert encoded[1] == 0
    assert encoded[2] == 2
    assert encoded[4] == 100

    decoded = decode_fields(specs, encoded)
    assert decoded["header_id"] == 1
    assert decoded["payload_len"] == 2
    assert decoded["data"] == 100
    assert decoded["computed"] == 200


# ---------------------------------------------------------------------------
# 6. Issue #331: Replayer timing and ReplayResult
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_replayer_result_and_capping():
    transport = VirtualTransport()
    replayer = SessionReplayer(transport, timing_mode=ReplayTimingMode.FAITHFUL, max_duration_s=0.05)
    assert replayer.max_gap_s is None  # faithful does not default to 5s cap

    # Replayer in capped mode has cap
    replayer_capped = SessionReplayer(transport, timing_mode=ReplayTimingMode.CAPPED)
    assert replayer_capped.max_gap_s == 5.0

    # Replay empty file returns ReplayResult
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write('{"timestamp": 0.0, "direction": "tx", "raw_hex": "aa", "length_bytes": 1}\n')
        f.write('{"timestamp": 10.0, "direction": "tx", "raw_hex": "bb", "length_bytes": 1}\n')
        tmp_name = f.name

    res = await replayer.replay_file(tmp_name)
    assert isinstance(res, ReplayResult)
    assert res.truncated is True
    assert res.frames_sent == 1
    assert int(res) == 1


# ---------------------------------------------------------------------------
# 7. Issue #332: Simulators
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_simulators_improvements():
    # ATModem exact match
    at_sim = ATModemSimulator()
    # Exact match works
    resp = at_sim.handle_delimited_command("AT+CSQ")
    assert b"+CSQ" in resp
    # Prefix with random letters does NOT match
    resp_malformed = at_sim.handle_delimited_command("AT+CSQFOO")
    assert b"ERROR" in resp_malformed

    # Modbus RTU framing and resynchronisation on CRC error
    modbus = ModbusRtuSimulator(slave_address=1)
    # Function 0x03: read 1 register at address 0
    # addr: 1, func: 3, start_reg: 0, count: 1
    body = bytes([1, 3, 0, 0, 0, 1])
    from omniuart.core.crc import calculate_crc
    req = body + calculate_crc(body, "crc16_modbus").to_bytes(2, "little")

    # Add bad noise bytes in front
    buf = bytearray(b"\xFF\xFE" + req)
    ans = modbus.process_incoming_bytes(buf)
    # First call encounters noise, slides buffer
    assert ans is None
    # Next call processes noise again, slides buffer
    ans = modbus.process_incoming_bytes(buf)
    assert ans is None
    # Now aligned to valid request
    ans = modbus.process_incoming_bytes(buf)
    assert ans is not None
    # Response contains byte count 2 and register value 1234 (0x04D2)
    assert bytes([1, 3, 2, 0x04, 0xD2]) in ans


# ---------------------------------------------------------------------------
# 8. Issue #334: Text protocol reply errors, operators, and retries
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_text_protocol_reply_and_operators():
    # Assert operators
    assert evaluate_assertion(StepAssertion(field="resp", op="contains", value="OK"), {"resp": "STATUS: OK NOW"}, {}).passed is True
    assert evaluate_assertion(StepAssertion(field="resp", op="startswith", value="+CSQ:"), {"resp": "+CSQ: 24,99"}, {}).passed is True
    assert evaluate_assertion(StepAssertion(field="resp", op="matches", value=r"\d+,\d+"), {"resp": "+CSQ: 24,99"}, {}).passed is True

    # Text protocol error detection & retry safety
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="TextProto", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.DELIMITED, suffix="\r\n"),
        commands=[
            CommandSpec(name="read_status", id="ERROR", safety=CommandSafety.READ_ONLY, response=ResponseSpec(timeout_ms=10)),
            CommandSpec(name="reboot", id="REBOOT_ERR", safety=CommandSafety.DESTRUCTIVE, response=ResponseSpec(timeout_ms=10, error_pattern="ERR")),
        ],
    )
    vt = VirtualTransport()
    await vt.open()
    session = SerialSession(spec, vt)

    # Destructive command returning error: retries=3 should be ignored (attempts=1) because it is destructive
    ex_dest = await session.send("reboot", retries=3)
    assert ex_dest.ok is False
    assert ex_dest.status == ExchangeStatus.INVALID_RESPONSE
    assert session.stats.total_requests == 1

    # Read-only command returning error: retries=2 should attempt 3 times
    ex_ro = await session.send("read_status", retries=2)
    assert ex_ro.ok is False
    assert session.stats.total_requests == 1 + 3
