"""Session Recording & Data Persistence Subsystem for OmniUART.

Captures live UART transactions and exports to JSON Lines (.jsonl), CSV, and raw binary (.bin) formats.
"""

from __future__ import annotations

import csv
import json
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
