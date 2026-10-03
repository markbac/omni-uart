"""Protocol conformance suite: every command of every bundled protocol is checked the same way (#209).

Golden vectors in ``golden/vectors.json`` pin the exact bytes and decoded structures. If a deliberate
codec change alters them, regenerate with ``PYTHONPATH=. python -m tests.conformance.generate_golden``
and review the diff.
"""

from __future__ import annotations

import json

import pytest

from omniuart.core.codec import CodecError, FrameCodec
from omniuart.core.models import FieldType
from tests.conformance.generate_golden import GOLDEN, build, jsonable
from tests.conformance.support import KNOWN_GAPS, command_cases, encode_request, sample_params, sample_value

CASES = [pytest.param(name, spec, cmd, id=f"{name}::{cmd.name}") for name, spec, cmd in command_cases()]


def skip_if_gap(name: str, cmd) -> None:
    if (name, cmd.name) in KNOWN_GAPS:
        pytest.skip(f"known gap: {KNOWN_GAPS[(name, cmd.name)]}")


def expected_gap_marks():
    return [
        pytest.param(name, spec, cmd, id=f"{name}::{cmd.name}",
                     marks=pytest.mark.xfail(reason=KNOWN_GAPS[(name, cmd.name)], strict=True) if (name, cmd.name) in KNOWN_GAPS else ())
        for name, spec, cmd in command_cases()
    ]


@pytest.mark.parametrize("name,spec,cmd", expected_gap_marks())
def test_request_round_trips(name, spec, cmd) -> None:
    codec = FrameCodec(spec)
    params = sample_params(cmd)
    frame = codec.decode(encode_request(spec, cmd, params), direction="request")
    assert frame.ok, frame.error
    assert frame.name == cmd.name
    for key, value in params.items():
        if key in frame.fields and isinstance(value, (int, float)) and not isinstance(value, bool):
            if codec.is_binary:
                assert frame.fields[key] == pytest.approx(value), key
            else:  # delimited text carries values as text
                assert str(frame.fields[key]) == str(value), key


@pytest.mark.parametrize("name,spec,cmd", CASES)
def test_boundary_values_encode_and_out_of_range_is_refused(name, spec, cmd) -> None:
    skip_if_gap(name, cmd)
    codec = FrameCodec(spec)
    for p in cmd.parameters:
        numeric = p.type.value.startswith(("uint", "int", "float")) and p.options is None
        if not numeric:
            continue
        for which in ("min", "max"):
            params = {**sample_params(cmd), p.name: sample_value(p, which)}
            assert codec.decode(encode_request(spec, cmd, params), direction="request").ok, (p.name, which)
        if p.min is not None:
            with pytest.raises(CodecError):
                encode_request(spec, cmd, {**sample_params(cmd), p.name: p.min - 1})
        if p.max is not None:
            with pytest.raises(CodecError):
                encode_request(spec, cmd, {**sample_params(cmd), p.name: p.max + 1})


@pytest.mark.parametrize("name,spec,cmd", CASES)
def test_corrupted_integrity_value_is_rejected(name, spec, cmd) -> None:
    skip_if_gap(name, cmd)
    codec = FrameCodec(spec)
    if not codec.is_binary or codec.integrity_size == 0:
        pytest.skip("no binary integrity field")
    raw = bytearray(encode_request(spec, cmd))
    pos = len(raw) - len(codec.footer_bytes) - 1  # last byte of the integrity value
    raw[pos] ^= 0xFF
    frame = codec.decode(bytes(raw), direction="request")
    assert not frame.ok


@pytest.mark.parametrize("name,spec,cmd", CASES)
def test_truncated_frame_is_never_reported_and_a_stream_of_frames_is_split(name, spec, cmd) -> None:
    skip_if_gap(name, cmd)
    codec = FrameCodec(spec)
    raw = encode_request(spec, cmd)
    for cut in range(len(raw)):
        frames, _ = codec.extract_frames(raw[:cut], direction="request")
        assert not any(f.ok for f in frames), f"cut at {cut}"
    frames, rest = codec.extract_frames(raw * 3, direction="request")
    if codec.is_binary or frames:  # a delimited protocol needs its terminator, which every frame carries
        assert [f.raw for f in frames if f.ok] == [raw] * 3 and rest == b""


@pytest.mark.parametrize("name,spec,cmd", CASES)
def test_response_round_trips_when_declared(name, spec, cmd) -> None:
    skip_if_gap(name, cmd)
    if cmd.response is None:
        pytest.skip("command has no response")
    codec = FrameCodec(spec)
    try:
        raw = codec.encode_response(cmd)
    except CodecError:
        pytest.skip("response cannot be built from field defaults")
    frame = codec.decode(raw, direction="response")
    assert frame.ok, frame.error


def test_golden_vectors_match_the_codec() -> None:
    committed = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(build())), "codec output changed: regenerate the golden vectors and review the diff"


def test_golden_vectors_decode_to_the_recorded_structure() -> None:
    committed = json.loads(GOLDEN.read_text(encoding="utf-8"))
    specs = {name: spec for name, spec, _ in command_cases()}
    checked = 0
    for name, commands in committed.items():
        codec = FrameCodec(specs[name])
        for command, entry in commands.items():
            frame = codec.decode(bytes.fromhex(entry["request"]), direction="request")
            assert frame.ok and frame.name == command and jsonable(frame.fields) == entry["decoded"], (name, command)
            checked += 1
    assert checked >= 100


def test_known_gaps_are_a_small_documented_minority() -> None:
    total = len(CASES)
    assert 0 < len(KNOWN_GAPS) <= total * 0.25
    assert all(FieldType and reason for reason in KNOWN_GAPS.values())
