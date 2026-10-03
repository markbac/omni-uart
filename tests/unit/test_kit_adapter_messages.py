"""Kit adapter message mapping: no invented commands, `responses` kept, ids normalised (#259)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from omniuart.core.kit_adapter import _normalise_id, parse_kit_protocol
from omniuart.core.models import load_protocol

EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples" / "protocols").glob("*.json"))
KIT_EXAMPLES = [p for p in EXAMPLES if "commandResponseModel" in json.loads(p.read_text(encoding="utf-8"))]


def _kit(**extra: Any) -> Dict[str, Any]:
    return {"title": "T", "version": "1", "physicalLayer": {"baudRate": 9600}, **extra}


@pytest.mark.parametrize("name", ["cobs", "mbus-long", "nmea0183"])
def test_stream_only_protocols_have_no_commands_and_expose_their_messages(name: str) -> None:
    spec = load_protocol(next(p for p in EXAMPLES if p.name.startswith(name)))
    assert spec.commands == []
    assert "ping" not in [c.name.lower() for c in spec.commands]
    assert spec.telemetry, "device-initiated messages must be kept"


def test_nmea_sentence_is_identified_by_its_constant_and_has_no_discriminator_parameter() -> None:
    spec = load_protocol(next(p for p in EXAMPLES if p.name.startswith("nmea0183")))
    gga = next(t for t in spec.telemetry if t.name == "GGA")
    assert gga.id == "GPGGA"
    assert "sentenceId" not in [f.name for f in gga.fields]


@pytest.mark.parametrize("path", KIT_EXAMPLES, ids=lambda p: p.name)
def test_every_kit_example_keeps_its_command_and_message_counts(path: Path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    spec = load_protocol(path)
    assert len(spec.commands) == len(raw.get("commands", []))
    assert len(spec.telemetry) == len(raw.get("responses", []))
    assert [c.name for c in spec.commands] == [c["name"] for c in raw.get("commands", [])]


def test_empty_definition_gets_no_invented_command() -> None:
    spec = parse_kit_protocol(_kit())
    assert spec.commands == [] and spec.telemetry == []


@pytest.mark.parametrize("raw, expected", [(1, 1), ("0x01", 1), ("0xFF", 255), ("17", 17), ("GPGGA", "GPGGA"), ("AT", "AT"), ("0xZZ", "0xZZ"), (True, "True")])
def test_ids_are_normalised_to_int_where_possible(raw: Any, expected: Any) -> None:
    assert _normalise_id(raw) == expected


def test_string_hex_constant_is_found_by_numeric_id() -> None:
    spec = parse_kit_protocol(
        _kit(
            commands=[{"name": "Read", "fields": [{"name": "op", "type": "uint", "sizeBytes": 1, "constValue": "0x01", "role": "discriminator"}]}],
            responses=[{"name": "Reply", "fields": [{"name": "op", "type": "uint", "sizeBytes": 1, "constValue": "0x81", "role": "discriminator"}]}],
        )
    )
    assert spec.get_command_by_id(1) is not None and spec.get_command_by_id(1).name == "Read"
    assert spec.telemetry[0].id == 0x81


def test_command_without_discriminator_falls_back_to_its_index_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        spec = parse_kit_protocol(_kit(commands=[{"name": "A", "fields": []}, {"name": "B", "fields": []}]), source_name="x.json")
    assert [c.id for c in spec.commands] == [0, 1]
    assert "no discriminator" in caplog.text


def test_info_and_docs_show_device_initiated_messages() -> None:
    from omniuart.cli import format_protocol_help
    from omniuart.docs_generator import generate_markdown_docs

    spec = load_protocol(next(p for p in EXAMPLES if p.name.startswith("nmea0183")))
    help_text = format_protocol_help(spec)
    assert "DEVICE-INITIATED MESSAGES" in help_text and "GGA (ID: GPGGA)" in help_text
    assert "no host-to-device commands" in help_text
    assert "## Device-Initiated Messages" in generate_markdown_docs(spec)
