"""Tests for the schema-driven FrameCodec (#189)."""

from pathlib import Path

import pytest

from omniuart.core.codec import CodecError, FrameCodec
from omniuart.core.crc import calculate_crc
from omniuart.core.models import load_protocol

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "protocols"


@pytest.fixture()
def sensor():
    return load_protocol(EXAMPLES / "binary_sensor_node.yaml")


@pytest.fixture()
def codec(sensor):
    return FrameCodec(sensor)


def test_command_frame_layout_and_real_crc(codec):
    frame = codec.encode_command("get_readings", {"channel": 2})
    # header | length (payload only, 1 byte of payload) | id | payload | crc16_modbus (LE) | footer
    assert frame[:2] == b"\xaa\x55"
    assert frame[2:4] == b"\x01\x00"
    assert frame[4] == 0x02 and frame[5] == 0x02
    assert frame[-2:] == b"\x55\xaa"
    crc = calculate_crc(frame[2:6], "crc16_modbus")
    assert frame[6:8] == crc.to_bytes(2, "little")
    assert frame[6:8] != (sum(frame[:6]) & 0xFFFF).to_bytes(2, "little")


def test_defaults_are_applied(codec):
    assert codec.encode_command("get_readings", {}) == codec.encode_command("get_readings", {"channel": 0})


def test_out_of_range_is_rejected_not_clamped(codec):
    with pytest.raises(CodecError, match="above the maximum"):
        codec.encode_command("get_readings", {"channel": 99})


def test_invalid_value_is_rejected_not_zeroed(codec):
    with pytest.raises(CodecError, match="expects an integer"):
        codec.encode_command("get_readings", {"channel": "abc"})


def test_enum_must_be_a_declared_option(codec):
    codec.encode_command("set_sampling_rate", {"rate_hz": 5})
    with pytest.raises(CodecError, match="not one of"):
        codec.encode_command("set_sampling_rate", {"rate_hz": 7})


def test_unknown_command_and_parameter(codec):
    with pytest.raises(CodecError, match="Unknown command"):
        codec.encode_command("nope")
    with pytest.raises(CodecError, match="Unknown parameter"):
        codec.encode_command("get_readings", {"chanel": 1})


def test_command_round_trip(codec):
    frame = codec.encode_command("get_readings", {"channel": 3})
    decoded = codec.decode(frame, direction="request")
    assert decoded.ok, decoded.error
    assert (decoded.kind, decoded.name, decoded.message_id) == ("command", "get_readings", 2)
    assert decoded.fields == {"channel": 3}


def test_response_round_trip_with_floats(codec):
    values = {"channel": 1, "temperature": 21.5, "humidity": 40.25, "pressure_hpa": 1013.0}
    frame = codec.encode_response("get_readings", values)
    decoded = codec.decode(frame, direction="response")
    assert decoded.ok, decoded.error
    assert (decoded.kind, decoded.name, decoded.message_id) == ("response", "get_readings", 0x82)
    assert decoded.fields == values


def test_telemetry_round_trip(codec):
    frame = codec.encode_telemetry("periodic_status", {"battery_millivolts": 3700, "error_flags": 4})
    decoded = codec.decode(frame, direction="response")
    assert decoded.ok, decoded.error
    assert (decoded.kind, decoded.name) == ("telemetry", "periodic_status")
    assert decoded.fields == {"battery_millivolts": 3700, "error_flags": 4}


def test_corrupted_crc_is_reported(codec):
    frame = bytearray(codec.encode_command("get_readings", {"channel": 1}))
    frame[5] ^= 0xFF
    decoded = codec.decode(bytes(frame), direction="request")
    assert not decoded.ok
    assert "integrity mismatch" in decoded.error


def test_stream_resync_skips_garbage_and_handles_split_frames(codec):
    f1 = codec.encode_command("ping")
    f2 = codec.encode_command("get_readings", {"channel": 1})
    stream = b"\x00\xaa\x13" + f1 + b"\xff" + f2
    frames, rest = codec.extract_frames(stream[:10], direction="request")
    assert frames == [] and rest.startswith(b"\xaa\x55")
    frames, rest = codec.extract_frames(rest + stream[10:], direction="request")
    assert [f.name for f in frames] == ["ping", "get_readings"]
    assert rest == b""


def test_partial_header_at_end_of_stream_is_kept(codec):
    frames, rest = codec.extract_frames(b"\x01\x02\xaa", direction="request")
    assert frames == [] and rest == b"\xaa"


@pytest.mark.parametrize(
    "includes, expected",
    [("payload_only", 1), ("payload_and_cmd", 2), ("full_frame", 2 + 2 + 1 + 1 + 2 + 2)],
)
def test_length_semantics(sensor, includes, expected):
    sensor.framing.length.includes = includes
    sensor.framing.length.type = "uint16"
    frame = FrameCodec(sensor).encode_command("get_readings", {"channel": 0})
    assert int.from_bytes(frame[2:4], "little") == expected
    assert FrameCodec(sensor).decode(frame, direction="request").ok


def test_length_field_width_follows_spec(sensor):
    sensor.framing.length.type = "uint8"
    codec = FrameCodec(sensor)
    frame = codec.encode_command("get_readings", {"channel": 1})
    assert frame[2] == 1 and frame[3] == 2  # one-byte length, then command id
    assert codec.decode(frame, direction="request").fields == {"channel": 1}


@pytest.mark.parametrize("covers", ["after_header", "full_frame", "payload_only"])
def test_integrity_coverage(sensor, covers):
    sensor.framing.integrity.covers = covers
    codec = FrameCodec(sensor)
    frame = codec.encode_command("get_readings", {"channel": 1})
    body = {"after_header": frame[2:6], "full_frame": frame[:6], "payload_only": frame[5:6]}[covers]
    assert frame[6:8] == calculate_crc(body, "crc16_modbus").to_bytes(2, "little")
    assert codec.decode(frame, direction="request").ok


def test_big_endian_and_wide_types():
    spec = load_protocol(
        """
schema_version: "1.0.0"
metadata: {name: Wide, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing:
  type: binary
  header: [0x7E]
  command_id: {type: uint16, endian: big}
  integrity: {algorithm: crc32, endian: big}
commands:
  - name: big
    id: 0x1234
    parameters:
      - {name: a, type: uint64, endian: big}
      - {name: b, type: int16, endian: big, min: -5, max: 5}
      - {name: c, type: bool}
      - {name: d, type: string, length: 4}
      - {name: e, type: bytes, length: 2}
"""
    )
    codec = FrameCodec(spec)
    frame = codec.encode_command("big", {"a": 2**63, "b": -3, "c": True, "d": "hi", "e": "0xBEEF"})
    assert frame[:3] == b"\x7e\x12\x34"
    assert frame[3:11] == (2**63).to_bytes(8, "big")  # integer, not ASCII digits
    decoded = codec.decode(frame, direction="request")
    assert decoded.ok, decoded.error
    assert decoded.fields == {"a": 2**63, "b": -3, "c": True, "d": "hi", "e": "beef"}
    with pytest.raises(CodecError):
        codec.encode_command("big", {"a": 1, "b": 9, "c": 0, "d": "x", "e": "00"})
    with pytest.raises(CodecError, match="longer than"):
        codec.encode_command("big", {"a": 1, "b": 1, "c": 0, "d": "toolong", "e": "00"})


def test_delimited_encoding_joins_parameters():
    spec = load_protocol(
        """
schema_version: "1.0.0"
metadata: {name: At, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing: {type: delimited, prefix: "AT+", delimiter: ",", suffix: "\\r\\n"}
commands:
  - name: set
    id: CFG
    parameters:
      - {name: x, type: uint8}
      - {name: y, type: string}
"""
    )
    codec = FrameCodec(spec)
    assert codec.encode_command("set", {"x": 1, "y": "z"}) == b"AT+CFG,1,z\r\n"
    frames, rest = codec.extract_frames(b"AT+CFG,1,z\r\nAT+CF", direction="request")
    assert frames[0].name == "set" and frames[0].fields == {"x": "1", "y": "z"}
    assert rest == b"AT+CF"


def test_unsupported_integrity_algorithm_is_an_error(sensor):
    sensor.framing.integrity.algorithm = "crc-99-bogus"
    with pytest.raises(CodecError, match="Unsupported CRC algorithm"):
        FrameCodec(sensor)
