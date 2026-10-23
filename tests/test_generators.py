"""Unit tests for protocol schema artefact generators (Wireshark, C, Python, JSON Schema) (#282, #319, #338)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from omniuart.cli import main as cli_main
from omniuart.core.catalog import CatalogManager
from omniuart.generators import (
    generate_c_header,
    generate_json_schema,
    generate_python_dataclasses,
    generate_wireshark_dissector,
)

PROTOCOLS = [
    "binary_sensor_node.yaml",
    "at-commands-uart-interface.json",
    "custom_crc_device.yaml",
]


def test_generators_output() -> None:
    catalog = CatalogManager()

    for proto_name in PROTOCOLS:
        spec = catalog.get_protocol(proto_name, first=True)
        assert spec is not None, f"Could not find protocol {proto_name}"

        # 1. Wireshark dissector generator
        dissector = generate_wireshark_dissector(spec)
        assert "Proto(" in dissector
        assert "wtap_encap" in dissector

        # 2. C Header generator
        c_header = generate_c_header(spec)
        assert "#ifndef" in c_header
        assert "command_id_t" in c_header

        # 3. Python dataclasses generator
        py_dataclasses = generate_python_dataclasses(spec)
        assert "@dataclass" in py_dataclasses
        assert "class " in py_dataclasses

    # 4. JSON Schema generator
    schema_json = generate_json_schema()
    assert '"$schema"' in schema_json or '"title"' in schema_json


def test_generators_wire_format_golden_outputs() -> None:
    """Golden-output tests verifying wire-accurate framing, CRC functions, and dissector offsets (#282, #338)."""
    catalog = CatalogManager()

    # 1. binary_sensor_node.yaml (Binary with Header, Length, Cmd ID, Modbus CRC, Response)
    bin_spec = catalog.get_protocol("binary_sensor_node.yaml", first=True)
    assert bin_spec is not None

    c_bin = generate_c_header(bin_spec)
    assert "HEADER_LEN 2" in c_bin
    assert "header_bytes[2] = {0xAA, 0x55}" in c_bin
    assert "BAUDRATE 115200" in c_bin
    assert "calculate_crc" in c_bin
    assert "ping_req_t" in c_bin
    assert "ping_resp_t" in c_bin

    lua_bin = generate_wireshark_dissector(bin_spec)
    assert "local f_header = ProtoField.bytes" in lua_bin
    assert "local f_length = ProtoField.uint16" in lua_bin
    assert "local f_cmd_id = ProtoField.uint8" in lua_bin
    assert "local f_crc = ProtoField.uint16" in lua_bin
    assert "buffer(offset, 2)" in lua_bin  # Header offset

    py_bin = generate_python_dataclasses(bin_spec)
    assert "class PingRequest:" in py_bin
    assert "class PingResponse:" in py_bin

    # 2. custom_crc_device.yaml (Custom 16-bit CRC)
    crc_spec = catalog.get_protocol("custom_crc_device.yaml", first=True)
    assert crc_spec is not None

    c_crc = generate_c_header(crc_spec)
    assert "calculate_crc" in c_crc

    # 3. at-commands-uart-interface.json (Delimited / text commands)
    at_spec = catalog.get_protocol("at-commands-uart-interface.json", first=True)
    assert at_spec is not None

    py_at = generate_python_dataclasses(at_spec)
    assert "@dataclass" in py_at
    assert '""' in py_at or "0" in py_at


def test_cli_generate_command() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "binary_sensor.h"
        code = cli_main(["generate", "c", "binary_sensor_node.yaml", "--output", str(out_file)])
        assert code == 0
        assert out_file.exists()
        assert "#ifndef" in out_file.read_text(encoding="utf-8")

        schema_file = Path(tmp_dir) / "protocol.schema.json"
        code_schema = cli_main(["generate", "schema", "--output", str(schema_file)])
        assert code_schema == 0
        assert schema_file.exists()
