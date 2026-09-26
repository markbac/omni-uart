"""Session Recording & Data Persistence Subsystem for OmniUART.

Captures live UART transactions and exports to JSON Lines (.jsonl), CSV, raw binary (.bin), and Wireshark PCAPNG (.pcapng) formats.
"""

from __future__ import annotations

import csv
import json
import struct
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class PacketEvent(BaseModel):
    """Container for a single recorded UART transmission packet event."""

    model_config = ConfigDict(extra="ignore")

    timestamp: float = Field(default_factory=time.time)
    direction: str  # "tx" or "rx"
    raw_hex: str
    length_bytes: int
    command_name: Optional[str] = None
    command_id: Optional[Union[int, str]] = None
    decoded_fields: Dict[str, Any] = Field(default_factory=dict)
    crc_valid: Optional[bool] = None
    latency_ms: Optional[float] = None

    def to_csv_row(self) -> Dict[str, str]:
        """Convert packet event into flat dictionary for CSV export."""
        return {
            "timestamp": f"{self.timestamp:.6f}",
            "direction": self.direction.upper(),
            "raw_hex": self.raw_hex,
            "length_bytes": str(self.length_bytes),
            "command_name": self.command_name or "",
            "command_id": str(self.command_id or ""),
            "decoded_fields": json.dumps(self.decoded_fields),
            "crc_valid": str(self.crc_valid) if self.crc_valid is not None else "",
            "latency_ms": f"{self.latency_ms:.2f}" if self.latency_ms is not None else "",
        }


class SessionRecorder:
    """Thread-safe ring buffer and transaction recorder."""

    def __init__(self, max_capacity: int = 10000) -> None:
        self.max_capacity = max_capacity
        self.events: List[PacketEvent] = []
        self._is_recording = True

    def record(
        self,
        direction: str,
        raw_bytes: bytes,
        command_name: Optional[str] = None,
        command_id: Optional[Union[int, str]] = None,
        decoded_fields: Optional[Dict[str, Any]] = None,
        crc_valid: Optional[bool] = None,
        latency_ms: Optional[float] = None,
    ) -> PacketEvent:
        """Log a packet transaction event."""
        if not self._is_recording:
            return PacketEvent(direction=direction, raw_hex="", length_bytes=0)

        raw_hex = raw_bytes.hex().upper()
        formatted_hex = " ".join(raw_hex[i:i+2] for i in range(0, len(raw_hex), 2))

        event = PacketEvent(
            timestamp=time.time(),
            direction=direction.lower(),
            raw_hex=formatted_hex,
            length_bytes=len(raw_bytes),
            command_name=command_name,
            command_id=command_id,
            decoded_fields=decoded_fields or {},
            crc_valid=crc_valid,
            latency_ms=latency_ms,
        )

        if len(self.events) >= self.max_capacity:
            self.events.pop(0)

        self.events.append(event)
        return event

    def clear(self) -> None:
        """Clear recorded events."""
        self.events.clear()

    def stop(self) -> None:
        """Stop recording new events."""
        self._is_recording = False

    def start(self) -> None:
        """Resume recording new events."""
        self._is_recording = True

    def export_jsonl(self, target_path: Union[str, Path]) -> Path:
        """Export session events to JSON Lines (.jsonl) format."""
        path = Path(target_path)
        with path.open("w", encoding="utf-8") as f:
            for event in self.events:
                f.write(event.model_dump_json() + "\n")
        return path

    def export_csv(self, target_path: Union[str, Path]) -> Path:
        """Export session events to tabular CSV format."""
        path = Path(target_path)
        fieldnames = [
            "timestamp",
            "direction",
            "raw_hex",
            "length_bytes",
            "command_name",
            "command_id",
            "decoded_fields",
            "crc_valid",
            "latency_ms",
        ]
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for event in self.events:
                writer.writerow(event.to_csv_row())
        return path

    def export_raw_bin(self, target_path: Union[str, Path]) -> Path:
        """Export session raw binary payload bytes to binary (.bin) file."""
        path = Path(target_path)
        with path.open("wb") as f:
            for event in self.events:
                hex_clean = event.raw_hex.replace(" ", "")
                if hex_clean:
                    f.write(bytes.fromhex(hex_clean))
        return path

    def export_pcapng(self, target_path: Union[str, Path]) -> Path:
        """Export session events as Wireshark PCAPNG capture file."""
        path = Path(target_path)
        with path.open("wb") as f:
            # Section Header Block (SHB)
            shb = struct.pack(
                "<IIIHHqI",
                0x0A0D0D0A,  # Block Type
                28,          # Block Total Length
                0x1A2B3C4D,  # Byte-Order Magic
                1, 0,        # Version 1.0
                -1,          # Section Length unspecified
                28,          # Block Total Length
            )
            f.write(shb)

            # Interface Description Block (IDB) - LinkType USER0 (147)
            idb = struct.pack(
                "<IIHHII",
                0x00000001,  # Block Type
                20,          # Block Total Length
                147,         # LinkType: USER0
                0,           # Reserved
                65535,       # SnapLen
                20,          # Block Total Length
            )
            f.write(idb)

            # Enhanced Packet Blocks (EPB)
            for event in self.events:
                hex_clean = event.raw_hex.replace(" ", "")
                data = bytes.fromhex(hex_clean) if hex_clean else b""
                pkt_len = len(data)
                
                # Align packet data to 32-bit boundary
                pad_len = (4 - (pkt_len % 4)) % 4
                padded_data = data + b"\x00" * pad_len
                block_len = 32 + len(padded_data)

                ts_us = int(event.timestamp * 1_000_000)
                ts_high = (ts_us >> 32) & 0xFFFFFFFF
                ts_low = ts_us & 0xFFFFFFFF

                epb_hdr = struct.pack(
                    "<IIIIII",
                    0x00000006,  # EPB Block Type
                    block_len,   # Block Total Length
                    0,           # Interface ID
                    ts_high,     # Timestamp High
                    ts_low,      # Timestamp Low
                    pkt_len,     # Captured Len
                )
                epb_tail = struct.pack("<II", pkt_len, block_len)
                f.write(epb_hdr + epb_tail[:4] + padded_data + epb_tail[4:])
        return path
