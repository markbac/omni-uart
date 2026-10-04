"""Unit tests for Pydantic data models and schema validation."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from omniuart.core.models import (
    FieldSpec,
    FieldType,
    FramingConfig,
    ProtocolSpec,
    ScriptSpec,
    SerialConfig,
    load_protocol,
    load_script,
)

EXAMPLES_PROTO_DIR = Path("examples/protocols")
EXAMPLES_SCRIPT_DIR = Path("examples/scripts")


def test_load_all_example_protocols() -> None:
    """Verify that all example YAML and JSON protocols parse and validate cleanly."""
    proto_files = list(EXAMPLES_PROTO_DIR.glob("*.*"))
    assert len(proto_files) >= 4, "Expected at least 4 example protocols"

    for proto_path in proto_files:
        protocol = load_protocol(proto_path)
        assert isinstance(protocol, ProtocolSpec)
        assert protocol.metadata.name
        assert protocol.metadata.version
        assert protocol.serial_config.baudrate > 0
        assert len(protocol.commands) + len(protocol.telemetry) >= 1  # stream-only protocols have no commands
        print(f"Verified protocol: {protocol.metadata.name} (version {protocol.metadata.version})")


def test_load_all_example_scripts() -> None:
    """Verify that all example YAML and JSON test scripts parse and validate cleanly."""
    script_files = list(EXAMPLES_SCRIPT_DIR.glob("*.*"))
    assert len(script_files) >= 2, "Expected at least 2 example scripts"

    for script_path in script_files:
        script = load_script(script_path)
        assert isinstance(script, ScriptSpec)
        assert script.meta.name
        assert script.meta.protocol
        assert len(script.steps) >= 1
        print(f"Verified script: {script.meta.name} ({len(script.steps)} steps)")


def test_invalid_baudrate_rejection() -> None:
    """Verify that non-positive baud rates raise validation errors (non-standard positive rates are allowed)."""
    with pytest.raises(ValidationError) as exc_info:
        SerialConfig(baudrate=0)
    assert "baudrate" in str(exc_info.value).lower()


def test_field_spec_defaults() -> None:
    """Verify default attribute values on FieldSpec."""
    field = FieldSpec(name="temp", type=FieldType.FLOAT32)
    assert field.endian == "little"
    assert field.unit is None
    assert field.min is None
    assert field.max is None
    assert field.scale is None


def test_invalid_framing_rejection() -> None:
    """Verify that invalid framing configurations raise validation errors."""
    with pytest.raises(ValidationError):
        FramingConfig(type="unsupported_framing")  # type: ignore


def test_custom_crc_model_extraction() -> None:
    """Verify extracting a CrcModel from a protocol with custom CRC."""
    custom_proto = load_protocol(EXAMPLES_PROTO_DIR / "custom_crc_device.yaml")
    assert custom_proto.framing.integrity is not None
    assert custom_proto.framing.integrity.algorithm == "custom"
    assert custom_proto.framing.integrity.width == 16
    assert custom_proto.framing.integrity.poly == 0x1021

    crc_model = custom_proto.framing.integrity.to_crc_model()
    assert crc_model is not None
    assert crc_model.width == 16
    assert crc_model.poly == 0x1021
    assert crc_model.endian == "big"


def test_lookup_command() -> None:
    """Verify command lookup by name and opcode."""
    proto = load_protocol(EXAMPLES_PROTO_DIR / "binary_sensor_node.yaml")
    cmd = proto.get_command("ping")
    assert cmd is not None
    assert cmd.id == 1

    cmd_by_id = proto.get_command_by_id(1)
    assert cmd_by_id is not None
    assert cmd_by_id.name == "ping"

    assert proto.get_command("nonexistent") is None
    assert proto.get_command_by_id(999) is None


def test_load_protocol_and_script_missing_file_raises_filenotfounderror() -> None:
    """Verify load_protocol and load_script raise FileNotFoundError for missing path strings."""
    with pytest.raises(FileNotFoundError):
        load_protocol("examples/protocols/does-not-exist.yaml")

    with pytest.raises(FileNotFoundError):
        load_script("examples/scripts/does-not-exist.yaml")


def test_custom_crc_invalid_check_vector_fails_load() -> None:
    """Verify that an incorrect check vector for a custom CRC fails model validation on load."""
    from omniuart.core.models import IntegritySpec
    with pytest.raises(ValueError, match="check value mismatch"):
        IntegritySpec(
            algorithm="custom",
            width=16,
            poly=0x1021,
            init=0xFFFF,
            refin=False,
            refout=False,
            xorout=0x0000,
            check=0x9999,  # incorrect check vector (expected 0x29B1 for CRC-16/CCITT-FALSE)
        )
