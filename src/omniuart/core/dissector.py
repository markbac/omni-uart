"""Protocol Dissection and Diagnostic Breakdown Engine for OmniUART (#216).

Deconstructs raw UART frame bytes into field boundaries, offsets, decoded values,
integrity checksums, and human-readable diagnostic text output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from omniuart.core.codec import FrameCodec, field_size
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

    cmd = spec.get_command(frame.name or "") if frame.name else None
    specs = cmd.parameters if cmd and direction == "request" else (cmd.response.fields if cmd and cmd.response else [])

    pos = 0
    # Add framing slice header if binary header declared
    if spec.framing and spec.framing.header:
        hdr_val = spec.framing.header
        hdr = bytes(hdr_val) if isinstance(hdr_val, list) else (hdr_val if isinstance(hdr_val, bytes) else str(hdr_val).encode("utf-8"))
        if frame_bytes.startswith(hdr):
            dissected.field_slices.append(
                FieldSlice("header", 0, len(hdr), hdr, hdr.hex(" ").upper(), "header")
            )
            pos += len(hdr)


    # Payload field slices
    payload = frame.payload
    payload_pos = 0
    for s in specs:
        sz = field_size(s) or (len(payload) - payload_pos)
        if payload_pos + sz <= len(payload):
            slice_bytes = payload[payload_pos : payload_pos + sz]
            decoded = frame.fields.get(s.name, slice_bytes.hex())
            dissected.field_slices.append(
                FieldSlice(s.name, pos + payload_pos, pos + payload_pos + sz, slice_bytes, decoded, str(s.type.value))
            )
            payload_pos += sz

    # CRC info if integrity model present
    if spec.framing and spec.framing.integrity and spec.framing.integrity.algorithm.lower() != "none":
        from omniuart.core.crc import parse_crc_bytes
        crc_bits = codec._crc_bits
        calc_val = frame.integrity_calculated
        recv_val = frame.integrity_received
        if calc_val is None or recv_val is None:
            try:
                trailer_crc = codec._integrity_width
                footer_len = len(codec._footer)
                if len(frame_bytes) >= trailer_crc + footer_len:
                    integrity = spec.framing.integrity
                    recv_bytes = frame_bytes[len(frame_bytes) - trailer_crc - footer_len : len(frame_bytes) - footer_len]
                    recv_val = parse_crc_bytes(recv_bytes, crc_bits, integrity.endian)
                    head, length_size, id_size = codec._layout()
                    payload_len = len(frame_bytes) - head - length_size - id_size - trailer_crc - footer_len
                    body_start = len(frame_bytes) - trailer_crc - footer_len - max(0, payload_len)
                    expected_bytes = codec._integrity_bytes(body_start, frame_bytes[: len(frame_bytes) - trailer_crc - footer_len])
                    calc_val = parse_crc_bytes(expected_bytes, crc_bits, integrity.endian)
            except Exception:
                pass
        calc = calc_val if calc_val is not None else 0
        recv = recv_val if recv_val is not None else 0
        dissected.crc_info = {
            "algorithm": spec.framing.integrity.algorithm,
            "valid": frame.ok and (calc == recv),
            "calculated": calc,
            "received": recv,
            "bits": crc_bits,
        }



    return dissected
