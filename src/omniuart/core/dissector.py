"""Protocol Dissection and Diagnostic Breakdown Engine for OmniUART (#216).

Deconstructs raw UART frame bytes into field boundaries, offsets, decoded values,
integrity checksums, and human-readable diagnostic text output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from omniuart.core.codec import CodecError, FrameCodec, decode_fields_with_layout
from omniuart.core.models import ProtocolSpec


@dataclass
class FieldSlice:
    """Byte slice boundary and decoded representation of a single frame field."""

    field_name: str
    start_offset: int
    end_offset: int
    raw_bytes: bytes
    decoded_value: Any
    field_type: str

    @property
    def length_bytes(self) -> int:
        return self.end_offset - self.start_offset

    @property
    def hex_str(self) -> str:
        return self.raw_bytes.hex(" ").upper()


@dataclass
class DissectedFrame:
    """Complete diagnostic breakdown of a frame."""

    raw_bytes: bytes
    protocol_name: str
    direction: str = "request"
    command_name: Optional[str] = None
    command_id: Optional[Union[int, str]] = None
    valid: bool = True
    error: Optional[str] = None
    field_slices: List[FieldSlice] = field(default_factory=list)
    crc_info: Optional[Dict[str, Any]] = None

    def format_diagnostic_text(self) -> str:
        """Format human-readable diagnostic tree and field breakdown."""
        lines = []
        lines.append("=" * 72)
        lines.append(f" FRAME DISSECTION: {self.protocol_name} ({len(self.raw_bytes)} bytes)")
        lines.append(f" Direction : {self.direction.upper()}")
        lines.append(f" Command   : {self.command_name or 'Unknown'} (ID: {self.command_id if self.command_id is not None else 'N/A'})")
        lines.append(f" Status    : {'VALID' if self.valid else 'INVALID (' + (self.error or '') + ')'}")
        lines.append("-" * 72)
        lines.append(f"{'OFFSET':<8} {'LEN':<4} {'FIELD NAME':<18} {'TYPE':<10} {'RAW BYTES':<14} DECODED VALUE")
        lines.append("-" * 72)

        for s in self.field_slices:
            off_str = f"{s.start_offset}..{s.end_offset - 1}" if s.length_bytes > 1 else str(s.start_offset)
            val_str = str(s.decoded_value)
            if len(val_str) > 24:
                val_str = val_str[:21] + "..."
            lines.append(f"{off_str:<8} {s.length_bytes:<4} {s.field_name:<18} {s.field_type:<10} {s.hex_str:<14} {val_str}")

        if self.crc_info:
            bits = self.crc_info.get("bits", 16)
            hex_width = max(2, (bits + 3) // 4)
            lines.append("-" * 72)
            lines.append(f" Integrity Check : {self.crc_info.get('algorithm', 'CRC')}")
            lines.append(f"   Calculated    : 0x{self.crc_info.get('calculated', 0):0{hex_width}X}")
            lines.append(f"   Received      : 0x{self.crc_info.get('received', 0):0{hex_width}X}")
            lines.append(f"   CRC Valid     : {self.crc_info.get('valid', False)}")

        lines.append("=" * 72)
        return "\n".join(lines)


def dissect_frame(spec: ProtocolSpec, frame_bytes: bytes, direction: str = "request") -> DissectedFrame:
    """Dissect frame_bytes according to spec framing and payload field definitions."""
    codec = FrameCodec(spec)
    frames, _ = codec.extract_frames(frame_bytes, direction=direction)

    dissected = DissectedFrame(
        raw_bytes=frame_bytes,
        protocol_name=spec.metadata.name,
        direction=direction,
    )

    if not frames:
        dissected.valid = False
        dissected.error = "No frame recognized by framing codec"
        return dissected

    frame = frames[0]
    dissected.command_name = frame.name
    dissected.command_id = frame.message_id
    dissected.valid = frame.ok
    dissected.error = frame.error

    found = codec._lookup(frame.message_id, direction) if frame.message_id is not None else None
    specs = found[1] if found else []

    # Binary frames: header | length | command_id | payload | integrity | footer (see codec.py)
    payload_start = 0
    if codec.is_binary:
        head, length_size, id_size = codec._layout()
        trailer = codec.integrity_size + len(codec.footer_bytes)
        parts = [("header", 0, head), ("length", head, head + length_size), ("command_id", head + length_size, head + length_size + id_size)]
        if len(frame.raw) >= head + length_size + id_size + trailer:
            parts += [
                ("integrity", len(frame.raw) - trailer, len(frame.raw) - len(codec.footer_bytes)),
                ("footer", len(frame.raw) - len(codec.footer_bytes), len(frame.raw)),
            ]
        for name, start, end in parts:
            if end > start:
                chunk = frame.raw[start:end]
                dissected.field_slices.append(FieldSlice(name, start, end, chunk, chunk.hex(" ").upper(), "framing"))
        payload_start = head + length_size + id_size

    # Payload field slices, laid out exactly as the codec decodes them (offsets and bit groups included)
    payload = frame.payload
    try:
        _, layout = decode_fields_with_layout(specs, payload)
    except CodecError:
        layout = []
    for field_spec, start, end in layout:
        slice_bytes = payload[start:end]
        decoded = frame.fields.get(field_spec.name, slice_bytes.hex())
        dissected.field_slices.append(
            FieldSlice(field_spec.name, payload_start + start, payload_start + end, slice_bytes, decoded, str(field_spec.type.value))
        )
    dissected.field_slices.sort(key=lambda sl: sl.start_offset)

    # Integrity values come from the codec's own check, so coverage and width rules match decoding (#329)
    if frame.integrity_calculated is not None and frame.integrity_received is not None:
        assert spec.framing.integrity is not None
        dissected.crc_info = {
            "algorithm": spec.framing.integrity.algorithm,
            "valid": frame.integrity_calculated == frame.integrity_received,
            "calculated": frame.integrity_calculated,
            "received": frame.integrity_received,
            "bits": codec._crc_bits,
        }

    return dissected
