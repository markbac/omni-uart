"""Unit tests for linter module and CLI lint/convert subcommands."""

import tempfile
from pathlib import Path
import pytest

from omniuart.cli import main as cli_main
from omniuart.linter import convert_protocol_to_kit, lint_protocol_file

PROTO_FILE = Path("examples/protocols/binary_sensor_node.yaml")


def test_lint_valid_protocol_file() -> None:
    """Verify linting a valid protocol file succeeds with zero errors."""
    is_valid, errors = lint_protocol_file(PROTO_FILE)
    assert is_valid
    assert len(errors) == 0


def test_lint_nonexistent_file() -> None:
    """Verify linting a nonexistent file fails gracefully."""
    is_valid, errors = lint_protocol_file("nonexistent_file.yaml")
    assert not is_valid
    assert len(errors) >= 1
    assert "not found" in errors[0].lower()


def test_convert_protocol_to_kit() -> None:
    """Verify converting a legacy protocol into kit schema dictionary."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_file = Path(tmp_dir) / "converted.json"
        kit_data = convert_protocol_to_kit(PROTO_FILE, output_path=out_file)

        assert out_file.exists()
        assert kit_data["title"] == "BinarySensorNode"
        assert kit_data["physicalLayer"]["baudRate"] == 115200
        assert len(kit_data["commands"]) >= 1


def test_cli_lint_and_convert_commands(capsys) -> None:
    """Verify CLI lint and convert subcommands."""
    # Test lint
    exit_code = cli_main(["lint", str(PROTO_FILE)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "VALID" in captured.out

    # Test convert
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "out.json"
        exit_code = cli_main(["convert", str(PROTO_FILE), "-o", str(out_path)])
        assert exit_code == 0
        assert out_path.exists()
