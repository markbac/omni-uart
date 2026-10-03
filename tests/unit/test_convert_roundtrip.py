"""`convert` must preserve what the kit format can express and refuse (or flag) the rest (#263)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from omniuart.cli import main
from omniuart.core.kit_adapter import parse_kit_protocol
from omniuart.core.models import load_protocol
from omniuart.linter import ConversionLossError, convert_protocol_to_kit, find_conversion_losses

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "protocols"

SIMPLE = {
    "metadata": {"name": "Simple", "version": "1.0.0", "author": "me"},
    "serial_config": {"baudrate": 9600},
    "framing": {"type": "delimited"},
    "commands": [
        {
            "name": "SET", "id": "SET", "description": "set it", "safety": "idempotent", "tags": ["a"],
            "parameters": [
                {"name": "level", "type": "uint8", "min": 0, "max": 9, "default": 3, "unit": "dB"},
                {"name": "mode", "type": "enum", "options": {"1": "on", "2": "off"}},
                {"name": "tag", "type": "string", "length": 4},
            ],
            "response": {"id": "OK", "timeout_ms": 250, "fields": [{"name": "result", "type": "string"}]},
        },
    ],
}


@pytest.fixture
def simple(tmp_path: Path) -> Path:
    path = tmp_path / "simple.yaml"
    path.write_text(yaml.safe_dump(SIMPLE))
    return path


def test_expressible_protocol_round_trips_exactly(simple: Path) -> None:
    kit = convert_protocol_to_kit(simple)  # would raise if anything were lost
    assert parse_kit_protocol(kit).model_dump() == load_protocol(simple).model_dump()


def test_types_ids_and_limits_survive(simple: Path) -> None:
    reloaded = parse_kit_protocol(convert_protocol_to_kit(simple))
    cmd = reloaded.get_command("SET")
    assert cmd.id == "SET" and cmd.response.id == "OK"
    level = cmd.parameters[0]
    assert (level.type.value, level.min, level.max, level.default, level.unit) == ("uint8", 0, 9, 3, "dB")
    assert cmd.safety.value == "idempotent"


@pytest.mark.parametrize("name", ["binary_sensor_node.yaml", "custom_crc_device.yaml", "smart_actuator.json", "ascii_device.yaml"])
def test_bundled_examples_report_what_is_lost(name: str) -> None:
    with pytest.raises(ConversionLossError) as info:
        convert_protocol_to_kit(EXAMPLES / name)
    assert info.value.losses  # never silent


def test_lossy_flag_converts_anyway(tmp_path: Path) -> None:
    out = tmp_path / "kit.json"
    kit = convert_protocol_to_kit(EXAMPLES / "binary_sensor_node.yaml", output_path=out, lossy=True)
    assert json.loads(out.read_text()) == kit


def test_cli_fails_without_lossy_and_writes_nothing(tmp_path: Path, capsys) -> None:
    out = tmp_path / "kit.json"
    assert main(["convert", str(EXAMPLES / "binary_sensor_node.yaml"), "-o", str(out)]) == 1
    assert not out.exists()
    assert "would lose" in capsys.readouterr().err


def test_cli_lossy_succeeds_with_warning(tmp_path: Path, capsys) -> None:
    out = tmp_path / "kit.json"
    assert main(["convert", str(EXAMPLES / "binary_sensor_node.yaml"), "-o", str(out), "--lossy"]) == 0
    assert out.exists() and "not preserved" in capsys.readouterr().err


def test_cli_exact_conversion_succeeds(simple: Path, capsys) -> None:
    assert main(["convert", str(simple)]) == 0
    assert json.loads(capsys.readouterr().out)["commands"][0]["name"] == "SET"


def test_find_conversion_losses_detects_an_unloadable_result(simple: Path) -> None:
    assert find_conversion_losses(load_protocol(simple), {"physicalLayer": {"baudRate": "x"}})[0].startswith("the converted")
