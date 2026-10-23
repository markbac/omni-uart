"""Register-style protocols: one read and one write command id, a data item id per register, NAK replies.

Covers ``length.includes: length_to_end``, ``fixed`` parameters that tell apart commands sharing an id,
responses decoded as the answer to the request that was sent, and declared ``error_replies``.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from omniuart.core.codec import CodecError, FrameCodec
from omniuart.core.models import LengthSpec, ProtocolSpec
from omniuart.core.session import DeviceSession, ExchangeStatus
from omniuart.core.transport import VirtualTransport

REGISTER_PROTOCOL = {
    "metadata": {"name": "RegisterDevice", "version": "1.0.0"},
    "serial_config": {"baudrate": 9600},
    "framing": {
        "type": "binary",
        "header": [0x7E],
        "length": {"type": "uint8", "includes": "length_to_end"},
        "command_id": {"type": "uint8"},
        "integrity": {"algorithm": "crc16_modbus"},
    },
    "error_replies": [
        {"id": 0x11, "name": "ErrRdLock", "description": "the register is locked"},
        {"id": 0x12, "name": "ErrRdUnknown", "description": "no such register"},
    ],
    "commands": [
        {
            "name": "read_serial",
            "id": 0x03,
            "safety": "read_only",
            "parameters": [{"name": "item", "type": "uint16", "fixed": 1}],
            "response": {"timeout_ms": 200, "fields": [{"name": "serial", "type": "string", "length": 8}]},
        },
        {
            "name": "read_contrast",
            "id": 0x03,
            "safety": "read_only",
            "parameters": [{"name": "item", "type": "uint16", "fixed": 353}],
            "response": {"timeout_ms": 200, "fields": [{"name": "contrast", "type": "uint8"}]},
        },
        {
            "name": "write_contrast",
            "id": 0x04,
            "safety": "idempotent",
            "parameters": [{"name": "item", "type": "uint16", "fixed": 353}, {"name": "contrast", "type": "uint8", "max": 63}],
            "response": {"timeout_ms": 200, "fields": []},
        },
    ],
}


@pytest.fixture()
def spec() -> ProtocolSpec:
    return ProtocolSpec.model_validate(REGISTER_PROTOCOL)


def test_length_counts_from_the_length_byte_to_the_end(spec: ProtocolSpec) -> None:
    frame = FrameCodec(spec).encode_command("write_contrast", {"contrast": 40})
    assert frame[:5] == bytes([0x7E, len(frame) - 1, 0x04, 0x61, 0x01])  # item 353 little endian
    assert frame[5] == 40


def test_fixed_parameters_are_sent_and_cannot_be_changed(spec: ProtocolSpec) -> None:
    codec = FrameCodec(spec)
    assert codec.encode_command("read_contrast") == codec.encode_command("read_contrast", {"item": 353})
    with pytest.raises(CodecError):
        codec.encode_command("read_contrast", {"item": 1})


def test_requests_sharing_an_id_decode_as_the_right_command(spec: ProtocolSpec) -> None:
    codec = FrameCodec(spec)
    stream = codec.encode_command("read_serial") + codec.encode_command("read_contrast") + codec.encode_command("write_contrast", {"contrast": 9})
    frames, rest = codec.extract_frames(stream, direction="request")
    assert rest == b""
    assert [(f.name, f.ok) for f in frames] == [("read_serial", True), ("read_contrast", True), ("write_contrast", True)]
    assert frames[2].fields == {"item": 353, "contrast": 9}


def test_responses_sharing_an_id_decode_as_the_answer_to_the_request(spec: ProtocolSpec) -> None:
    async def go():
        async with DeviceSession(spec, VirtualTransport(spec, latency_ms=0.1, jitter_ms=0)) as session:
            return [await session.send(name) for name in ("read_serial", "read_contrast")] + [
                await session.send("write_contrast", {"contrast": 30})
            ]

    serial, contrast, write = asyncio.run(go())
    assert serial.ok and set(serial.fields) == {"serial"}
    assert contrast.ok and set(contrast.fields) == {"contrast"}
    assert write.ok and write.fields == {}


def test_a_declared_error_reply_ends_the_exchange_as_a_device_error(spec: ProtocolSpec) -> None:
    transport = VirtualTransport(spec, latency_ms=0.1, jitter_ms=0)
    transport.register_response(0x03, FrameCodec(spec).encode_message(0x11, b""))

    async def go():
        async with DeviceSession(spec, transport) as session:
            return await session.send("read_contrast")

    exchange = asyncio.run(go())
    assert exchange.status is ExchangeStatus.DEVICE_ERROR
    assert "ErrRdLock" in (exchange.error or "") and "locked" in (exchange.error or "")


def test_length_includes_is_validated() -> None:
    with pytest.raises(ValidationError):
        LengthSpec(type="uint8", includes="whole_thing")
