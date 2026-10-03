"""The generic simulator keeps incomplete data and recovers from garbage (#206)."""

from __future__ import annotations

import pytest

from omniuart.core.codec import FrameCodec
from omniuart.core.models import load_protocol
from omniuart.core.simulator import BaseDeviceSimulator
from tests.unit.test_schema_simulator import LAYOUTS


@pytest.fixture(params=sorted(LAYOUTS))
def rig(request):
    spec = load_protocol(LAYOUTS[request.param])
    return BaseDeviceSimulator(spec=spec), FrameCodec(spec), spec


def feed(sim, buf: bytearray, data: bytes):
    buf.extend(data)
    return sim.process_incoming_bytes(buf)


def test_every_split_point_yields_exactly_one_response(rig) -> None:
    sim, codec, _ = rig
    request, expected = codec.encode_command("read", {}), codec.encode_response("read")
    for cut in range(1, len(request)):
        buf, out = bytearray(), b""
        out += feed(sim, buf, request[:cut]) or b""
        assert out == b"", f"answered after only {cut} of {len(request)} bytes"
        out += feed(sim, buf, request[cut:]) or b""
        assert out == expected, f"split at {cut}"
        assert not buf


def test_byte_at_a_time_answers_only_when_complete(rig) -> None:
    sim, codec, _ = rig
    request, expected = codec.encode_command("read", {}), codec.encode_response("read")
    buf, outputs = bytearray(), []
    for b in request:
        outputs.append(feed(sim, buf, bytes([b])))
    assert outputs[:-1] == [None] * (len(request) - 1)
    assert outputs[-1] == expected


def test_split_header_is_kept_across_reads() -> None:
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])  # header AA 55
    sim, codec = BaseDeviceSimulator(spec=spec), FrameCodec(spec)
    request = codec.encode_command("read", {})
    buf = bytearray()
    assert feed(sim, buf, request[:1]) is None and bytes(buf) == request[:1]
    assert feed(sim, buf, request[1:]) == codec.encode_response("read")


def test_multiple_frames_in_one_read_each_get_a_response(rig) -> None:
    sim, codec, _ = rig
    request, expected = codec.encode_command("read", {}), codec.encode_response("read")
    assert feed(sim, bytearray(), request * 3) == expected * 3


def test_corrupt_frame_followed_by_valid_frame_still_answers_the_valid_one(rig) -> None:
    sim, codec, _ = rig
    good = codec.encode_command("read", {})
    bad = bytearray(good)
    bad[-2 if len(good) > 3 else -1] ^= 0xFF
    out = feed(sim, bytearray(), bytes(bad) + good)
    assert out == codec.encode_response("read")


def test_garbage_before_a_frame_is_skipped() -> None:
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])
    sim, codec = BaseDeviceSimulator(spec=spec), FrameCodec(spec)
    assert feed(sim, bytearray(), b"\x00\x13\xAA\x01" + codec.encode_command("read", {})) == codec.encode_response("read")


def test_pending_buffer_is_bounded() -> None:
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])
    sim = BaseDeviceSimulator(spec=spec)
    buf = bytearray(b"\xAA\x55\xFF\xFF" + b"\x00" * 100_000)  # a header promising a huge frame
    sim.process_incoming_bytes(buf)
    assert len(buf) <= sim.MAX_PENDING_BYTES
