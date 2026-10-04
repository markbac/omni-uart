"""Session Recording & Data Persistence Subsystem for OmniUART.

Captures live UART transactions and exports to JSON Lines (.jsonl), CSV, raw binary (.bin), and Wireshark PCAPNG (.pcapng) formats.
"""

from __future__ import annotations

from collections import deque
import csv
import json
import struct
import threading
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
        cmd_id_str = str(self.command_id) if self.command_id is not None else ""
        return {
            "timestamp": f"{self.timestamp:.6f}",
            "direction": self.direction.upper(),
            "raw_hex": self.raw_hex,
            "length_bytes": str(self.length_bytes),
            "command_name": self.command_name or "",
            "command_id": cmd_id_str,
            "decoded_fields": json.dumps(self.decoded_fields),
            "crc_valid": str(self.crc_valid) if self.crc_valid is not None else "",
            "latency_ms": f"{self.latency_ms:.2f}" if self.latency_ms is not None else "",
        }


class Transaction(BaseModel):
    """Pairing of outbound command frame and inbound response frame(s)."""

    model_config = ConfigDict(extra="ignore")

    transaction_id: str
    command_name: Optional[str] = None
    command_id: Optional[Union[int, str]] = None
    tx_event: Optional[PacketEvent] = None
    rx_events: List[PacketEvent] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    status: str = "ok"

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class SessionRecord(BaseModel):
    """Structured session log containing metadata, transactions, and event stream."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(default_factory=lambda: f"session_{int(time.time()*1000)}")
    protocol_name: Optional[str] = None
    start_time: float = Field(default_factory=time.time)
    end_time: Optional[float] = None
    transport_metadata: Dict[str, Any] = Field(default_factory=dict)
    events: List[PacketEvent] = Field(default_factory=list)
    transactions: List[Transaction] = Field(default_factory=list)


class SessionRecorder:
    """Thread-safe ring buffer, transaction recorder, and session exporter."""

    def __init__(self, max_capacity: int = 10000, protocol_name: Optional[str] = None, transport_metadata: Optional[Dict[str, Any]] = None) -> None:
        self.max_capacity = max_capacity
        self._events: deque[PacketEvent] = deque(maxlen=max_capacity)
        self._transactions: List[Transaction] = []
        self.session_record = SessionRecord(
            protocol_name=protocol_name,
            transport_metadata=transport_metadata or {},
        )
        self._lock = threading.Lock()
        self._is_recording = True


    @property
    def events(self) -> List[PacketEvent]:
        """Return a thread-safe snapshot copy of recorded events."""
        with self._lock:
            return list(self._events)

    def record(
        self,
        direction: str,
        raw_bytes: bytes,
        command_name: Optional[str] = None,
        command_id: Optional[Union[int, str]] = None,
        decoded_fields: Optional[Dict[str, Any]] = None,
        crc_valid: Optional[bool] = None,
        latency_ms: Optional[float] = None,
    ) -> Optional[PacketEvent]:
        """Log a packet transaction event. Returns None if recording is currently stopped."""
        with self._lock:
            if not self._is_recording:
                return None

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

            self._events.append(event)
            return event

    def add_event(self, event: PacketEvent) -> None:
        """Add an existing PacketEvent to the ring buffer."""
        with self._lock:
            if self._is_recording and event is not None:
                self._events.append(event)

    def clear(self) -> None:
        """Clear recorded events."""
        with self._lock:
            self._events.clear()

    def stop(self) -> None:
        """Stop recording new events."""
        with self._lock:
            self._is_recording = False

    def start(self) -> None:
        """Resume recording new events."""
        with self._lock:
            self._is_recording = True

    @property
    def transactions(self) -> List[Transaction]:
        """Return a thread-safe snapshot copy of recorded transactions."""
        with self._lock:
            return list(self._transactions)

    def add_transaction(self, transaction: Transaction) -> None:
        """Add a Transaction record to the session log."""
        with self._lock:
            if self._is_recording and transaction is not None:
                self._transactions.append(transaction)

    def export_session_json(self, target_path: Union[str, Path]) -> Path:
        """Export full structured SessionRecord (metadata, transactions, events) to JSON."""
        path = Path(target_path)
        with self._lock:
            self.session_record.end_time = time.time()
            self.session_record.events = list(self._events)
            self.session_record.transactions = list(self._transactions)
            dump = self.session_record.model_dump_json(indent=2)
        path.write_text(dump, encoding="utf-8")
        return path

    def export_jsonl(self, target_path: Union[str, Path]) -> Path:
        """Export session events to JSON Lines (.jsonl) format."""
        path = Path(target_path)
        events_snapshot = self.events
        with path.open("w", encoding="utf-8") as f:
            for event in events_snapshot:
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
        events_snapshot = self.events
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for event in events_snapshot:
                writer.writerow(event.to_csv_row())
        return path

    def export_raw_bin(self, target_path: Union[str, Path]) -> Path:
        """Export session raw binary payload bytes to binary (.bin) file."""
        path = Path(target_path)
        events_snapshot = self.events
        with path.open("wb") as f:
            for event in events_snapshot:
                hex_clean = event.raw_hex.replace(" ", "")
                if hex_clean:
                    f.write(bytes.fromhex(hex_clean))
        return path

    def export_pcapng(self, target_path: Union[str, Path]) -> Path:
        """Export session events as Wireshark PCAPNG capture file with EPB direction flags."""
        path = Path(target_path)
        events_snapshot = self.events
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
            for event in events_snapshot:
                hex_clean = event.raw_hex.replace(" ", "")
                data = bytes.fromhex(hex_clean) if hex_clean else b""
                pkt_len = len(data)

                # Align packet data to 32-bit boundary
                pad_len = (4 - (pkt_len % 4)) % 4
                padded_data = data + b"\x00" * pad_len

                # Direction flags option: 1 = inbound (rx), 2 = outbound (tx)
                dir_flag = 1 if event.direction.lower() == "rx" else 2
                opt_epb_flags = struct.pack("<HHI", 2, 4, dir_flag) + struct.pack("<HH", 0, 0)

                # EPB block length: 32 bytes fixed header/lengths + padded_data + 12 bytes options
                block_len = 32 + len(padded_data) + len(opt_epb_flags)

                ts_us = int(event.timestamp * 1_000_000)
                ts_high = (ts_us >> 32) & 0xFFFFFFFF
                ts_low = ts_us & 0xFFFFFFFF

                epb_hdr = struct.pack(
                    "<IIIIIII",
                    0x00000006,  # EPB Block Type
                    block_len,   # Block Total Length
                    0,           # Interface ID
                    ts_high,     # Timestamp High
                    ts_low,      # Timestamp Low
                    pkt_len,     # Captured Len
                    pkt_len,     # Original Packet Len
                )
                epb_tail = struct.pack("<I", block_len)
                f.write(epb_hdr + padded_data + opt_epb_flags + epb_tail)
        return path
