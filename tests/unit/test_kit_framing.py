"""Kit sync/length framing maps onto the native header and length model, or is refused by name (#311)."""

from __future__ import annotations

import logging

import pytest

from omniuart.core.codec import FrameCodec
from omniuart.core.kit_adapter import parse_kit_protocol


def kit(framing: dict, **extra) -> dict:
    return {
        "title": "T", "version": "1",
        "physicalLayer": {"baudRate": 9600},
        "encoding": {"byteOrder": extra.pop("byte_order", "little-endian")},
        "framing": {"style": "sync-length-payload-crc", **framing},
        "integrityCheck": {"algorithm": "crc-16-modbus"},
        "commands": [{
            "name": "Ping",
            "fields": [{"name": "type", "type": "uint", "sizeBytes": 1, "constValue": 7, "role": "discriminator"},
                       {"name": "value", "type": "uint", "sizeBytes": 2}],
        }],
        **extra,
    }


def test_plain_sync_and_payload_length_are_mapped() -> None:
    spec = parse_kit_protocol(kit({"syncBytes": [0x7E], "lengthField": {"sizeBytes": 2, "countsFrom": "payload-only"}}, byte_order="big-endian"))
    assert spec.framing.header == [0x7E]
    assert (spec.framing.length.type, spec.framing.length.endian, spec.framing.length.includes) == ("uint16", "big", "payload_and_cmd")
    raw = FrameCodec(spec).encode_command("Ping", {"value": 1})
    assert raw[:3] == bytes([0x7E, 0x00, 0x03])  # sync, then id + 2 value bytes counted
    frame = FrameCodec(spec).decode(raw, direction="request")
    assert frame.ok and frame.fields["value"] == 1


def test_whole_frame_length_is_mapped() -> None:
    spec = parse_kit_protocol(kit({"syncBytes": [0x01], "lengthField": {"sizeBytes": 1, "countsFrom": "whole-frame"}}))
    assert spec.framing.length.includes == "full_frame"
    codec = FrameCodec(spec)
    raw = codec.encode_command("Ping", {"value": 1})
    assert raw[1] == len(raw) and codec.decode(raw, direction="request").ok


@pytest.mark.parametrize(
    "extra,named",
    [
        ({"lengthField": {"sizeBytes": 1, "countsFrom": "payload-only", "precedingHeaderBytes": 2}}, "precedingHeaderBytes"),
        ({"lengthField": {"sizeBytes": 1, "countsFrom": "payload-only", "repeated": True}}, "repeated"),
        ({"lengthField": {"sizeBytes": 1, "countsFrom": "length-field-to-crc-inclusive"}}, "countsFrom"),
        ({"lengthField": {"sizeBytes": 1, "countsFrom": "payload-only"}, "preLengthHeaderBytes": 2}, "preLengthHeaderBytes"),
        ({"lengthField": {"sizeBytes": 1, "countsFrom": "payload-only"}, "escapeByte": 0x7D}, "escapeByte"),
    ],
)
def test_unrepresentable_framing_is_not_approximated_and_is_named(extra, named, caplog) -> None:
    with caplog.at_level(logging.WARNING):
        spec = parse_kit_protocol(kit({"syncBytes": [0x7E], **extra}), source_name="x.json")
    assert spec.framing.header is None and spec.framing.length is None
    assert named in caplog.text and "x.json" in caplog.text
