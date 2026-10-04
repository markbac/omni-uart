"""Unit tests for protocol schema artefact generators (Wireshark, C, Python, JSON Schema)."""

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
