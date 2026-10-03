"""Property-based tests of the frame codec (#210)."""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from omniuart.core.codec import FrameCodec
from omniuart.core.models import load_protocol
from tests.unit.test_schema_simulator import LAYOUTS

pytestmark = pytest.mark.filterwarnings("ignore")
SETTINGS = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])

CODECS = {name: FrameCodec(load_protocol(text)) for name, text in LAYOUTS.items()}
layout = st.sampled_from(sorted(CODECS))
channel_layouts = ["header_length_crc_footer", "no_header_big_endian_sum8"]


def decode_stream(codec: FrameCodec, chunks) -> list:
    buf, frames = b"", []
    for chunk in chunks:
        found, buf = codec.extract_frames(buf + chunk, direction="request")
        frames.extend(found)
    return frames


@SETTINGS
@given(name=st.sampled_from(channel_layouts), ch=st.integers(0, 3))
def test_encode_decode_round_trip(name, ch) -> None:
    codec = CODECS[name]
    frame = codec.decode(codec.encode_command("read", {"ch": ch}), direction="request")
    assert frame.ok and frame.name == "read" and frame.fields == {"ch": ch}


@SETTINGS
@given(name=layout, count=st.integers(1, 5), data=st.data())
def test_chunking_never_changes_the_frames_found(name, count, data) -> None:
    codec = CODECS[name]
    stream = codec.encode_command("read", {}) * count
    cuts = sorted(data.draw(st.lists(st.integers(0, len(stream)), max_size=8)))
    chunks = [stream[a:b] for a, b in zip([0, *cuts], [*cuts, len(stream)], strict=True)]
    whole = decode_stream(codec, [stream])
    pieces = decode_stream(codec, chunks)
    assert [f.raw for f in pieces] == [f.raw for f in whole]
    assert len(whole) == count and all(f.ok for f in whole)


@SETTINGS
@given(name=layout, data=st.data())
def test_a_truncated_frame_is_never_reported(name, data) -> None:
    codec = CODECS[name]
    frame = codec.encode_command("read", {})
    cut = data.draw(st.integers(0, len(frame) - 1))
    frames, rest = codec.extract_frames(frame[:cut], direction="request")
    assert frames == [] and len(rest) <= cut


@SETTINGS
@given(name=layout, data=st.data())
def test_a_single_bit_flip_never_yields_a_valid_frame(name, data) -> None:
    codec = CODECS[name]
    frame = bytearray(codec.encode_command("read", {}))
    pos = data.draw(st.integers(0, len(frame) - 1))
    frame[pos] ^= 1 << data.draw(st.integers(0, 7))
    frames, _ = codec.extract_frames(bytes(frame), direction="request")
    assert not any(f.ok for f in frames)


@SETTINGS
@given(name=layout, noise=st.binary(max_size=300))
def test_arbitrary_bytes_never_raise_and_never_grow_the_buffer(name, noise) -> None:
    codec = CODECS[name]
    frames, rest = codec.extract_frames(noise, direction="any")
    assert len(rest) <= len(noise)
    assert all(isinstance(f.raw, bytes) for f in frames)


@SETTINGS
@given(name=layout, noise=st.binary(max_size=60), count=st.integers(1, 3))
def test_valid_frames_survive_leading_garbage_of_non_header_bytes(name, noise, count) -> None:
    codec = CODECS[name]
    good = codec.encode_command("read", {})
    first = good[:1]
    noise = bytes(b for b in noise if b != first[0]) if codec._header else b""  # noqa: SLF001 - header resync
    frames = decode_stream(codec, [noise + good * count])
    assert sum(1 for f in frames if f.ok and f.raw == good) == count
