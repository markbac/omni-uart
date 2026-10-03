"""The generic simulator and VirtualTransport are driven by the protocol schema (#190)."""

import asyncio

import pytest

from omniuart.core.codec import FrameCodec
from omniuart.core.models import load_protocol
from omniuart.core.simulator import BaseDeviceSimulator
from omniuart.core.transport import VirtualSerialPair, VirtualTransport

LAYOUTS = {
    "header_length_crc_footer": """
schema_version: "1.0.0"
metadata: {name: A, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing:
  type: binary
  header: [0xAA, 0x55]
  length: {type: uint16, endian: little, includes: payload_only}
  command_id: {type: uint8}
  integrity: {algorithm: crc16_modbus}
  footer: [0x55, 0xAA]
commands:
  - name: read
    id: 0x07
    parameters: [{name: ch, type: uint8, min: 0, max: 3, default: 0}]
    response:
      id: 0x87
      fields: [{name: value, type: uint16, endian: little, default: 513}]
  - name: silent
    id: 0x09
""",
    "no_header_big_endian_sum8": """
schema_version: "1.0.0"
metadata: {name: B, version: "1.0.0"}
serial_config: {baudrate: 9600}
framing:
  type: binary
  command_id: {type: uint16, endian: big}
  integrity: {algorithm: sum8}
commands:
  - name: read
    id: 0x0102
    parameters: [{name: ch, type: uint8, default: 1}]
    response:
      id: 0x8102
      fields: [{name: value, type: uint32, endian: big, default: 258}]
""",
    "uint8_length_full_frame_xor": """
schema_version: "1.0.0"
metadata: {name: C, version: "1.0.0"}
serial_config: {baudrate: 57600}
framing:
  type: binary
  header: [0x7E]
  length: {type: uint8, includes: full_frame}
  command_id: {type: uint8}
  integrity: {algorithm: xor, covers: full_frame}
commands:
  - name: read
    id: 0x30
    response:
      id: 0xB0
      fields: [{name: value, type: uint16, endian: big, default: 4660}]
""",
}


EXPECTED_VALUE = {
    "header_length_crc_footer": 513,
    "no_header_big_endian_sum8": 258,
    "uint8_length_full_frame_xor": 4660,
}


async def _exchange(spec, writes, wait=0.4):
    pair = VirtualSerialPair()
    await pair.open()
    sim = BaseDeviceSimulator(spec=spec, transport=pair.device, latency_ms=0)
    await sim.start()
    try:
        for chunk in writes:
            await pair.host.write(chunk)
        await asyncio.sleep(wait)
        got = await pair.host.read(size=1024, timeout_ms=100)
        return got, sim
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("layout", sorted(LAYOUTS))
async def test_simulator_answers_through_the_codec(layout):
    spec = load_protocol(LAYOUTS[layout])
    codec = FrameCodec(spec)
    request = codec.encode_command("read", {})
    got, sim = await _exchange(spec, [request])
    expected = codec.encode_response("read")
    assert got == expected
    reply = codec.decode(got, direction="response")
    assert reply.ok and reply.fields == {"value": EXPECTED_VALUE[layout]}
    assert sim._state["rx_count"] == 1


@pytest.mark.asyncio
async def test_one_response_per_frame_even_when_written_byte_by_byte():
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])
    codec = FrameCodec(spec)
    request = codec.encode_command("read", {"ch": 2})
    got, sim = await _exchange(spec, [bytes([b]) for b in request])
    assert got == codec.encode_response("read")


@pytest.mark.asyncio
async def test_two_frames_in_one_write_get_two_responses():
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])
    codec = FrameCodec(spec)
    got, _ = await _exchange(spec, [codec.encode_command("read", {}) * 2])
    assert got == codec.encode_response("read") * 2


@pytest.mark.asyncio
async def test_corrupt_unknown_and_response_less_requests_are_not_answered():
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])
    codec = FrameCodec(spec)
    corrupt = bytearray(codec.encode_command("read", {}))
    corrupt[-4] ^= 0xFF
    unknown = codec.encode_message(0x55, b"")
    silent = codec.encode_command("silent")
    got, sim = await _exchange(spec, [bytes(corrupt), unknown, silent])
    assert got == b""
    assert sim._state["rx_errors"] == 2  # corrupt CRC and unknown id


@pytest.mark.asyncio
async def test_handle_command_hook_controls_response_values():
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])

    class Sim(BaseDeviceSimulator):
        def handle_command(self, cmd, params):
            return {"value": 1000 + params["ch"]}

    pair = VirtualSerialPair()
    await pair.open()
    sim = Sim(spec=spec, transport=pair.device, latency_ms=0)
    await sim.start()
    try:
        codec = FrameCodec(spec)
        await pair.host.write(codec.encode_command("read", {"ch": 3}))
        got = await pair.host.read(size=64, timeout_ms=500)
        assert codec.decode(got, direction="response").fields == {"value": 1003}
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_virtual_transport_with_protocol_answers_from_schema():
    spec = load_protocol(LAYOUTS["no_header_big_endian_sum8"])
    codec = FrameCodec(spec)
    transport = VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0)
    await transport.open()
    await transport.write(codec.encode_command("read", {}))
    expected = codec.encode_response("read")
    assert await transport.read(size=len(expected), timeout_ms=500) == expected
    await transport.write(b"\x01\x02\x03")  # not a frame: no response
    assert await transport.read(size=1, timeout_ms=50) == b""
    await transport.close()


@pytest.mark.asyncio
async def test_virtual_transport_without_protocol_is_a_plain_loopback():
    transport = VirtualTransport(latency_ms=1.0, jitter_ms=0.0)
    await transport.open()
    await transport.write(b"hello")
    assert await transport.read(size=5, timeout_ms=500) == b"hello"
    await transport.close()
