"""Schema-driven frame codec: encode commands and responses, decode and re-synchronise streams.

The codec is the single implementation of the OmniUART wire format. The CLI, web API, desktop GUI,
simulator, fuzzer and script runner all build and parse frames through :class:`FrameCodec` so that
they agree on field order, length semantics, integrity coverage and value encoding.

Binary frame layout (every part except the payload is optional and driven by ``framing``)::

    header | length | command_id | payload | integrity | footer

Delimited frame layout::

    prefix | command_id [delimiter param]... | suffix
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from omniuart.core.limits import get_limits
from omniuart.core.crc import (
    byte_order,
    algorithm_width,
    calculate_crc,
    format_crc_bytes,
    parse_crc_bytes,
)
from omniuart.core.models import (
    CommandSpec,
    FieldSpec,
    FieldType,
    FramingType,
    ProtocolSpec,
)

_INT_FORMATS: Dict[FieldType, Tuple[str, int, bool]] = {
    FieldType.UINT8: ("B", 1, False),
    FieldType.UINT16: ("H", 2, False),
    FieldType.UINT32: ("I", 4, False),
    FieldType.UINT64: ("Q", 8, False),
    FieldType.INT8: ("b", 1, True),
    FieldType.INT16: ("h", 2, True),
    FieldType.INT32: ("i", 4, True),
    FieldType.INT64: ("q", 8, True),
}
_FLOAT_FORMATS: Dict[FieldType, Tuple[str, int]] = {
    FieldType.FLOAT32: ("f", 4),
    FieldType.FLOAT64: ("d", 8),
}
_LENGTH_SIZES = {"uint8": 1, "uint16": 2, "uint32": 4}
INTEGRITY_COVERAGE = ("after_header", "full_frame", "payload_only")


class CodecError(ValueError):
    """Raised when a value or frame cannot be encoded or decoded according to the protocol."""


@dataclass
class DecodedFrame:
    """A frame parsed from the wire.

    ``error`` is ``None`` for a valid frame. For a frame whose envelope was recognised but is
    invalid (bad integrity value, truncated payload, undecodable fields) ``error`` describes why
    and ``fields`` is empty, so callers can count it as rejected rather than silently dropping it.
    """

    raw: bytes
    kind: str = "unknown"  # "command", "response", "telemetry" or "unknown"
    message_id: Optional[Union[int, str]] = None
    name: Optional[str] = None
    payload: bytes = b""
    fields: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _as_int(value: Union[int, str], what: str) -> int:
    if isinstance(value, bool):
        raise CodecError(f"{what} must be an integer, got {value!r}")
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip(), 0)
    except ValueError:
        raise CodecError(f"{what} must be an integer, got {value!r}") from None


def _as_bytes(value: Union[List[int], str, None]) -> bytes:
    if value is None:
        return b""
    if isinstance(value, list):
        return bytes(value)
    text = value.strip()
    if text.lower().startswith("0x"):
        text = text[2:]
    return bytes.fromhex(text.replace(" ", ""))


def _order(endian: str) -> str:
    return ">" if endian == "big" else "<"


def field_size(spec: FieldSpec) -> Optional[int]:
    """Return the encoded size in bytes of a field, or ``None`` when it is variable length."""
    if spec.type in _INT_FORMATS:
        return _INT_FORMATS[spec.type][1]
    if spec.type in _FLOAT_FORMATS:
        return _FLOAT_FORMATS[spec.type][1]
    if spec.type in (FieldType.BOOL, FieldType.ENUM):
        return 1
    return spec.length  # string / bytes: fixed only when ``length`` is declared


def encode_value(spec: FieldSpec, value: Any) -> bytes:
    """Encode one value strictly. Invalid or out-of-range values raise :class:`CodecError`."""
    name = spec.name
    ftype = spec.type
    if value is None:
        raise CodecError(f"Parameter '{name}' has no value")

    if ftype in _INT_FORMATS or ftype is FieldType.ENUM:
        if isinstance(value, bool) or isinstance(value, float) and not float(value).is_integer():
            raise CodecError(f"Parameter '{name}' expects an integer, got {value!r}")
        try:
            number = _as_int(value, f"Parameter '{name}'") if isinstance(value, str) else int(value)
        except (TypeError, ValueError):
            raise CodecError(f"Parameter '{name}' expects an integer, got {value!r}") from None
        if spec.min is not None and number < spec.min:
            raise CodecError(f"Parameter '{name}' value {number} is below the minimum {spec.min:g}")
        if spec.max is not None and number > spec.max:
            raise CodecError(f"Parameter '{name}' value {number} is above the maximum {spec.max:g}")
        if ftype is FieldType.ENUM:
            if spec.options is not None and str(number) not in {str(k) for k in spec.options}:
                raise CodecError(f"Parameter '{name}' value {number} is not one of {sorted(map(str, spec.options))}")
            code, size, signed = "B", 1, False
        else:
            code, size, signed = _INT_FORMATS[ftype]
        low, high = (-(1 << (8 * size - 1)), (1 << (8 * size - 1)) - 1) if signed else (0, (1 << (8 * size)) - 1)
        if not low <= number <= high:
            raise CodecError(f"Parameter '{name}' value {number} does not fit {ftype.value} ({low}..{high})")
        return struct.pack(_order(spec.endian) + code, number)

    if ftype in _FLOAT_FORMATS:
        code, _ = _FLOAT_FORMATS[ftype]
        try:
            number_f = float(value)
        except (TypeError, ValueError):
            raise CodecError(f"Parameter '{name}' expects a number, got {value!r}") from None
        if math.isnan(number_f) or math.isinf(number_f):
            raise CodecError(f"Parameter '{name}' must be finite, got {value!r}")
        if spec.min is not None and number_f < spec.min:
            raise CodecError(f"Parameter '{name}' value {number_f:g} is below the minimum {spec.min:g}")
        if spec.max is not None and number_f > spec.max:
            raise CodecError(f"Parameter '{name}' value {number_f:g} is above the maximum {spec.max:g}")
        try:
            return struct.pack(_order(spec.endian) + code, number_f)
        except (OverflowError, struct.error):
            raise CodecError(f"Parameter '{name}' value {number_f:g} does not fit {ftype.value}") from None

    if ftype is FieldType.BOOL:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("1", "true", "yes", "on"):
                return b"\x01"
            if lowered in ("0", "false", "no", "off"):
                return b"\x00"
            raise CodecError(f"Parameter '{name}' expects a boolean, got {value!r}")
        return b"\x01" if bool(value) else b"\x00"

    if ftype is FieldType.STRING:
        data = str(value).encode("utf-8")
    else:  # BYTES
        if isinstance(value, (bytes, bytearray)):
            data = bytes(value)
        else:
            try:
                data = _as_bytes(str(value))
            except ValueError:
                raise CodecError(f"Parameter '{name}' expects hex bytes, got {value!r}") from None
    if spec.length is not None:
        if len(data) > spec.length:
            raise CodecError(f"Parameter '{name}' is {len(data)} bytes, longer than its fixed length {spec.length}")
        data = data.ljust(spec.length, b"\x00")
    return data


def decode_value(spec: FieldSpec, data: bytes) -> Any:
    """Decode one value whose bytes have already been sliced to the field size."""
    ftype = spec.type
    if ftype in _INT_FORMATS:
        return struct.unpack(_order(spec.endian) + _INT_FORMATS[ftype][0], data)[0]
    if ftype in _FLOAT_FORMATS:
        return struct.unpack(_order(spec.endian) + _FLOAT_FORMATS[ftype][0], data)[0]
    if ftype is FieldType.ENUM:
        return data[0]
    if ftype is FieldType.BOOL:
        return data[0] != 0
    if ftype is FieldType.STRING:
        return data.rstrip(b"\x00").decode("utf-8", errors="replace")
    return data.hex()


def encode_fields(specs: Sequence[FieldSpec], values: Mapping[str, Any]) -> bytes:
    """Encode ``values`` in declaration order, applying declared defaults for omitted fields."""
    known = {s.name for s in specs}
    unknown = sorted(set(values) - known)
    if unknown:
        raise CodecError(f"Unknown parameter(s): {', '.join(unknown)}")
    out = bytearray()
    for spec in specs:
        if spec.name in values:
            value = values[spec.name]
        elif spec.default is not None:
            value = spec.default
        else:
            raise CodecError(f"Missing value for parameter '{spec.name}'")
        out.extend(encode_value(spec, value))
    return bytes(out)


def decode_fields(specs: Sequence[FieldSpec], data: bytes) -> Dict[str, Any]:
    """Decode ``data`` as a sequence of fields. Trailing or missing bytes raise :class:`CodecError`."""
    out: Dict[str, Any] = {}
    pos = 0
    for index, spec in enumerate(specs):
        size = field_size(spec)
        if size is None:
            if index != len(specs) - 1:
                raise CodecError(f"Variable-length field '{spec.name}' must be the last field")
            size = len(data) - pos
        if pos + size > len(data):
            raise CodecError(f"Payload too short for field '{spec.name}' ({len(data) - pos} of {size} bytes)")
        out[spec.name] = decode_value(spec, data[pos : pos + size])
        pos += size
    if pos != len(data):
        raise CodecError(f"{len(data) - pos} unexpected trailing payload byte(s)")
    return out


def validate_fields(specs: Sequence[FieldSpec], values: Mapping[str, Any]) -> Optional[str]:
    """Check decoded values against declared ``min``/``max``/``options``; return the first violation."""
    for spec in specs:
        value = values.get(spec.name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if spec.min is not None and value < spec.min:
            return f"'{spec.name}' value {value:g} is below the minimum {spec.min:g}"
        if spec.max is not None and value > spec.max:
            return f"'{spec.name}' value {value:g} is above the maximum {spec.max:g}"
        if spec.type is FieldType.ENUM and spec.options and str(int(value)) not in {str(k) for k in spec.options}:
            return f"'{spec.name}' value {value:g} is not a declared option"
    return None


def default_value(spec: FieldSpec) -> Any:
    """A valid placeholder value for a field: its declared default, else the smallest legal value."""
    if spec.default is not None:
        return spec.default
    if spec.type is FieldType.BOOL:
        return False
    if spec.type is FieldType.ENUM:
        return next(iter(spec.options), 0) if spec.options else 0
    if spec.type is FieldType.STRING:
        return ""
    if spec.type is FieldType.BYTES:
        return b"\x00" * (spec.length or 0)
    value = 0.0
    if spec.min is not None and value < spec.min:
        value = spec.min
    if spec.max is not None and value > spec.max:
        value = spec.max
    return int(value) if spec.type in _INT_FORMATS else float(value)


class FrameCodec:
    """Encode and decode frames for one :class:`ProtocolSpec`."""

    def __init__(self, spec: ProtocolSpec) -> None:
        self.spec = spec
        self.framing = spec.framing
        self.is_binary = self.framing.type is FramingType.BINARY
        self._header = _as_bytes(self.framing.header) if self.is_binary else b""
        self._max_frame = get_limits().frame_bytes
        self._footer = _as_bytes(self.framing.footer) if self.is_binary else b""
        self._crc_bits = self._resolve_integrity_width() if self.is_binary else 0
        self._integrity_width = self._crc_bits // 8  # bytes on the wire

    @property
    def integrity_size(self) -> int:
        """Size in bytes of the integrity field on the wire (0 when there is none)."""
        return self._integrity_width

    @property
    def footer_bytes(self) -> bytes:
        """The footer sequence of binary frames (empty when there is none)."""
        return self._footer

    # ------------------------------------------------------------------ integrity
    def _resolve_integrity_width(self) -> int:
        """Integrity field width in bits (0 when the protocol has no integrity field)."""
        integrity = self.framing.integrity
        if integrity is None or integrity.algorithm.lower() == "none":
            return 0
        try:
            return algorithm_width(integrity.algorithm, integrity.to_crc_model())
        except ValueError as exc:
            raise CodecError(str(exc)) from None

    def _integrity_bytes(self, body_start: int, frame: bytes) -> bytes:
        integrity = self.framing.integrity
        assert integrity is not None
        coverage = getattr(integrity, "covers", "after_header")
        if coverage == "full_frame":
            data = frame
        elif coverage == "payload_only":
            data = frame[body_start:]
        else:
            data = frame[len(self._header) :]
        try:
            value = calculate_crc(
                data,
                integrity.algorithm,
                custom_model=integrity.to_crc_model(),
                transform=integrity.transform,
                carry_wrap=integrity.carry_wrap,
            )
        except ValueError as exc:
            raise CodecError(str(exc)) from None
        return format_crc_bytes(value, self._crc_bits, integrity.endian)

    # ------------------------------------------------------------------ lookup
    def _command(self, command: Union[str, CommandSpec]) -> CommandSpec:
        if isinstance(command, CommandSpec):
            return command
        found = self.spec.get_command(command)
        if found is None:
            raise CodecError(f"Unknown command '{command}'")
        return found

    # ------------------------------------------------------------------ encode
    def encode_command(self, command: Union[str, CommandSpec], params: Optional[Mapping[str, Any]] = None) -> bytes:
        """Build the complete wire frame for a command."""
        cmd = self._command(command)
        payload = encode_fields(cmd.parameters, params or {})
        return self.encode_message(cmd.id, payload, params=[str(v) for v in self._text_params(cmd, params or {})])

    def encode_response(self, command: Union[str, CommandSpec], values: Optional[Mapping[str, Any]] = None) -> bytes:
        """Build the wire frame a device sends in answer to ``command``.

        Response fields missing from ``values`` fall back to :func:`default_value`.
        """
        cmd = self._command(command)
        if cmd.response is None:
            raise CodecError(f"Command '{cmd.name}' defines no response")
        merged = {f.name: default_value(f) for f in cmd.response.fields}
        merged.update(values or {})
        payload = encode_fields(cmd.response.fields, merged)
        message_id = cmd.response.id if cmd.response.id is not None else cmd.id
        return self.encode_message(message_id, payload)

    def encode_telemetry(self, name: str, values: Optional[Mapping[str, Any]] = None) -> bytes:
        """Build an unsolicited telemetry frame."""
        for tel in self.spec.telemetry:
            if tel.name == name:
                return self.encode_message(tel.id, encode_fields(tel.fields, values or {}))
        raise CodecError(f"Unknown telemetry frame '{name}'")

    @staticmethod
    def _text_params(cmd: CommandSpec, params: Mapping[str, Any]) -> List[Any]:
        out = []
        for spec in cmd.parameters:
            out.append(params.get(spec.name, spec.default))
        return out

    def encode_message(self, message_id: Union[int, str], payload: bytes, params: Optional[List[str]] = None) -> bytes:
        """Wrap an already encoded payload (or text parameters) in the protocol envelope."""
        if not self.is_binary:
            return self._encode_delimited(message_id, params or [])

        id_spec = self.framing.command_id
        id_size = 2 if id_spec and id_spec.type == "uint16" else 4 if id_spec and id_spec.type == "uint32" else 1
        id_bytes = b""
        if id_spec is not None or isinstance(message_id, int):
            number = _as_int(message_id, "Command id")
            if not 0 <= number < 1 << (8 * id_size):
                raise CodecError(f"Command id {number} does not fit {id_size} byte(s)")
            id_bytes = number.to_bytes(id_size, byte_order(id_spec.endian if id_spec else "little"))

        length_bytes = b""
        length_spec = self.framing.length
        if length_spec is not None:
            size = _LENGTH_SIZES.get(length_spec.type)
            if size is None:
                raise CodecError(f"Unsupported length field type '{length_spec.type}'")
            if length_spec.includes == "payload_and_cmd":
                value = len(id_bytes) + len(payload)
            elif length_spec.includes == "full_frame":
                value = (
                    len(self._header) + size + len(id_bytes) + len(payload) + self._integrity_width + len(self._footer)
                )
            else:
                value = len(payload)
            if value >= 1 << (8 * size):
                raise CodecError(f"Length {value} does not fit {length_spec.type}")
            length_bytes = value.to_bytes(size, byte_order(length_spec.endian))

        frame = bytearray(self._header + length_bytes + id_bytes + payload)
        if self._integrity_width:
            body_start = len(frame) - len(payload)
            frame.extend(self._integrity_bytes(body_start, bytes(frame)))
        frame.extend(self._footer)
        return bytes(frame)

    def line_terminator(self) -> str:
        """Line terminator of a delimited frame: ``suffix``, else a declared ``footer``, else CRLF."""
        if self.framing.suffix is not None:
            return self.framing.suffix
        if self.framing.footer:
            return _as_bytes(self.framing.footer).decode("utf-8", errors="replace")
        return "\r\n"

    def _encode_delimited(self, message_id: Union[int, str], params: List[str]) -> bytes:
        framing = self.framing
        delimiter = framing.delimiter if framing.delimiter is not None else ","
        suffix = self.line_terminator()
        text = (framing.prefix or "") + str(message_id)
        if params:
            text += delimiter + delimiter.join(params)
        return (text + suffix).encode("utf-8")

    # ------------------------------------------------------------------ decode
    def decode(self, data: bytes, direction: str = "any") -> DecodedFrame:
        """Decode exactly one complete frame. ``direction`` is ``request``, ``response`` or ``any``."""
        frames, rest = self.extract_frames(data, direction=direction)
        if len(frames) != 1 or rest:
            return DecodedFrame(raw=bytes(data), error="input is not exactly one complete frame")
        return frames[0]

    def extract_frames(self, data: Union[bytes, bytearray], direction: str = "any") -> Tuple[List[DecodedFrame], bytes]:
        """Pull every complete frame out of ``data`` and return ``(frames, unconsumed_bytes)``.

        Bytes before a header are discarded (resynchronisation). Frames whose envelope is intact
        but whose content is invalid are returned with ``error`` set instead of being dropped.
        """
        if not self.is_binary:
            return self._extract_delimited(bytes(data), direction)
        buf = bytes(data)
        frames: List[DecodedFrame] = []
        while True:
            start = buf.find(self._header) if self._header else 0
            if start < 0:
                keep = self._partial_header_len(buf)
                return frames, buf[len(buf) - keep :] if keep else b""
            buf = buf[start:]
            total = self._frame_length(buf)
            if total is None:
                return frames, buf
            if total < 0:  # impossible length: skip this header byte and resynchronise
                buf = buf[1:]
                continue
            raw, buf = buf[:total], buf[total:]
            frames.append(self._decode_frame(raw, direction))

    def _partial_header_len(self, buf: bytes) -> int:
        for size in range(min(len(self._header) - 1, len(buf)), 0, -1):
            if buf.endswith(self._header[:size]):
                return size
        return 0

    def _layout(self) -> Tuple[int, int, int]:
        id_spec = self.framing.command_id
        id_size = 2 if id_spec and id_spec.type == "uint16" else 4 if id_spec and id_spec.type == "uint32" else 1
        length_size = _LENGTH_SIZES.get(self.framing.length.type, 2) if self.framing.length else 0
        return len(self._header), length_size, id_size

    def _frame_length(self, buf: bytes) -> Optional[int]:
        """Total frame length, ``None`` if more bytes are needed, ``-1`` if the header is bogus."""
        head, length_size, id_size = self._layout()
        trailer = self._integrity_width + len(self._footer)
        if self.framing.length is not None:
            if len(buf) < head + length_size:
                return None
            value = int.from_bytes(buf[head : head + length_size], byte_order(self.framing.length.endian))
            includes = self.framing.length.includes
            if includes == "full_frame":
                total = value
                if total < head + length_size + id_size + trailer:
                    return -1
            elif includes == "payload_and_cmd":
                total = head + length_size + value + trailer
                if value < id_size:
                    return -1
            else:
                total = head + length_size + id_size + value + trailer
            if total > self._max_frame:
                return -1  # a declared length beyond the limit is treated as a false header
            return total if len(buf) >= total else None
        if self._footer:
            idx = buf.find(self._footer, head + id_size + self._integrity_width)
            if idx < 0:
                return -1 if len(buf) > self._max_frame else None
            return idx + len(self._footer)
        if len(buf) < head + id_size:
            return None
        message = self._lookup(int.from_bytes(buf[head : head + id_size], byte_order(self._id_endian())), "any")
        size = self._fixed_payload_size(message[1]) if message else None
        if size is None:
            return -1
        total = head + id_size + size + trailer
        return total if len(buf) >= total else None

    def _id_endian(self) -> str:
        return self.framing.command_id.endian if self.framing.command_id else "little"

    def _fixed_payload_size(self, fields: Optional[Sequence[FieldSpec]]) -> Optional[int]:
        if fields is None:
            return None
        total = 0
        for spec in fields:
            size = field_size(spec)
            if size is None:
                return None
            total += size
        return total

    def _lookup(self, message_id: Union[int, str], direction: str) -> Optional[Tuple[Tuple[str, str], List[FieldSpec]]]:
        """Return ``((kind, name), fields)`` for a message id."""
        if direction in ("request", "any"):
            for cmd in self.spec.commands:
                if self._same_id(cmd.id, message_id):
                    return ("command", cmd.name), cmd.parameters
        if direction in ("response", "any"):
            for cmd in self.spec.commands:
                if cmd.response is not None and cmd.response.id is not None and self._same_id(cmd.response.id, message_id):
                    return ("response", cmd.name), cmd.response.fields
            for tel in self.spec.telemetry:
                if self._same_id(tel.id, message_id):
                    return ("telemetry", tel.name), tel.fields
            if direction == "response":
                # A response that reuses the command id (no explicit response id declared).
                for cmd in self.spec.commands:
                    if cmd.response is not None and cmd.response.id is None and self._same_id(cmd.id, message_id):
                        return ("response", cmd.name), cmd.response.fields
        return None

    @staticmethod
    def _same_id(declared: Union[int, str], actual: Union[int, str]) -> bool:
        try:
            return _as_int(declared, "id") == _as_int(actual, "id")
        except CodecError:
            return str(declared) == str(actual)

    def _decode_frame(self, raw: bytes, direction: str) -> DecodedFrame:
        head, length_size, id_size = self._layout()
        trailer_crc = self._integrity_width
        footer_len = len(self._footer)
        if footer_len and not raw.endswith(self._footer):
            return DecodedFrame(raw=raw, error="missing footer")
        body = raw[head + length_size : len(raw) - trailer_crc - footer_len]
        if len(body) < id_size:
            return DecodedFrame(raw=raw, error="frame too short")
        message_id: Union[int, str] = int.from_bytes(body[:id_size], byte_order(self._id_endian()))
        payload = body[id_size:]
        frame = DecodedFrame(raw=raw, message_id=message_id, payload=payload)

        if trailer_crc:
            integrity = self.framing.integrity
            assert integrity is not None
            received_bytes = raw[len(raw) - trailer_crc - footer_len : len(raw) - footer_len]
            received = parse_crc_bytes(received_bytes, self._crc_bits, integrity.endian)
            expected = parse_crc_bytes(
                self._integrity_bytes(len(raw) - trailer_crc - footer_len - len(payload), raw[: len(raw) - trailer_crc - footer_len]),
                self._crc_bits,
                integrity.endian,
            )
            if received != expected:
                frame.error = f"integrity mismatch: received {received:#x}, expected {expected:#x}"
                return frame

        found = self._lookup(message_id, direction)
        if found is None:
            frame.error = f"unknown message id {message_id:#x}"
            return frame
        (frame.kind, frame.name), fields = found
        try:
            frame.fields = decode_fields(fields, payload)
        except CodecError as exc:
            frame.error = str(exc)
        return frame

    def _extract_delimited(self, data: bytes, direction: str) -> Tuple[List[DecodedFrame], bytes]:
        suffix = self.line_terminator().encode("utf-8")
        frames: List[DecodedFrame] = []
        buf = data
        while suffix and (idx := buf.find(suffix)) >= 0:
            line, buf = buf[:idx], buf[idx + len(suffix) :]
            text = line.decode("utf-8", errors="replace")
            prefix = self.framing.prefix or ""
            if prefix and not text.startswith(prefix):
                frames.append(DecodedFrame(raw=line + suffix, kind="response", payload=line, fields={"text": text}))
                continue
            body = text[len(prefix) :]
            delimiter = self.framing.delimiter if self.framing.delimiter is not None else ","
            head, _, rest = body.partition(delimiter) if delimiter else (body, "", "")
            frame = DecodedFrame(raw=line + suffix, kind="command", message_id=head, payload=rest.encode("utf-8"))
            cmd = next((c for c in self.spec.commands if str(c.id) == head), None)
            if cmd is not None:
                frame.name = cmd.name
                values = rest.split(delimiter) if rest else []
                frame.fields = {p.name: v for p, v in zip(cmd.parameters, values, strict=False)}
            frames.append(frame)
        return frames, buf


def build_frame_payload(spec: ProtocolSpec, cmd: CommandSpec, params: Mapping[str, Any]) -> bytes:
    """Build the raw wire frame for a command with the shared codec.

    Raises :class:`CodecError` for missing, unknown, out-of-range or otherwise invalid parameters
    instead of transmitting a guessed value.
    """
    return FrameCodec(spec).encode_command(cmd, params)
