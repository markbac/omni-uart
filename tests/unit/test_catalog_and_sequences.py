"""Unit tests for CatalogManager auto-discovery and sequence script parsing."""

import tempfile
from pathlib import Path
import pytest

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import ScriptSpec, load_script
from omniuart.core.sequence_adapter import load_kit_sequence, parse_kit_sequence

KIT_SEQUENCES_DIR = Path("../uart-interface-schema-kit/kit/examples/sequences")


def test_load_ubx_sequence() -> None:
    """Verify loading UBX baud rate switch sequence into ScriptSpec."""
    ubx_seq_file = KIT_SEQUENCES_DIR / "ubx-baud-switch-sequence.json"
    if ubx_seq_file.exists():
        script = load_script(ubx_seq_file)
        assert isinstance(script, ScriptSpec)
        assert script.meta.protocol == "ubx-uart-interface.json"
        assert len(script.steps) == 3

        # Step 1: Poll current port config
        assert script.steps[0].command == "CFG-PRT-Poll"
        assert script.steps[0].expect_response == "CFG-PRT-Poll"
        assert script.steps[0].timeout_ms == 200

        # Step 2: Request new baud rate with variable substitution
        assert script.steps[1].command == "CFG-PRT-SetBaud"
        assert script.steps[1].params.get("baudRate") == 115200

        # Step 3: Wait step
        assert script.steps[2].command is None
        assert script.steps[2].delay_ms == 100


def test_g460_sequence_exclusion() -> None:
    """Verify that G460 sequence files are explicitly rejected when loading."""
    g460_seq_file = KIT_SEQUENCES_DIR / "g460-smoke-test-sequence.json"
    if g460_seq_file.exists():
        with pytest.raises(ValueError, match="G460 sequence is explicitly excluded"):
            load_script(g460_seq_file)


def test_catalog_manager_auto_discovery() -> None:
    """Verify CatalogManager discovers protocols and scripts across registered directories."""
    catalog = CatalogManager()
    summary = catalog.catalog_summary()

    assert summary["protocols_found"] >= 4, f"Expected at least 4 protocols, got {summary['protocols_found']}"
    assert summary["scripts_found"] >= 1, f"Expected at least 1 script, got {summary['scripts_found']}"

    # Verify lookup of local example
    binary_sensor = catalog.get_protocol("binary_sensor_node.yaml")
    assert binary_sensor is not None


def test_catalog_manager_dynamic_pickup() -> None:
    """Verify that adding a new protocol file to a directory is automatically picked up by CatalogManager."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        catalog = CatalogManager(protocol_dirs=[tmp_path], script_dirs=[tmp_path])

        assert len(catalog.list_protocol_files()) == 0

        # Add a new protocol definition file dynamically
        new_proto_file = tmp_path / "custom_sensor_uart_interface.json"
        new_proto_file.write_text(
            """{
                "title": "Custom Sensor Protocol",
                "version": "1.0.0",
                "physicalLayer": {"baudRate": 9600},
                "commands": [{"name": "read_data", "id": 1}]
            }""",
            encoding="utf-8",
        )

        # Catalog immediately discovers the newly added file
        discovered_files = catalog.list_protocol_files()
        assert len(discovered_files) == 1
        assert discovered_files[0].name == "custom_sensor_uart_interface.json"

        proto = catalog.get_protocol("custom_sensor_uart_interface.json")
        assert proto is not None
        assert proto.metadata.name == "Custom Sensor Protocol"
        assert proto.serial_config.baudrate == 9600
