"""Unit tests for SessionRecorder and export engines (JSONL, CSV, RAW .bin)."""

import tempfile
from pathlib import Path
import pytest

from omniuart.core.recorder import PacketEvent, SessionRecorder


def test_session_recorder_and_exporters() -> None:
    """Verify recording packet events and exporting to JSONL, CSV, and RAW .bin formats."""
    recorder = SessionRecorder()
    assert len(recorder.events) == 0

    # Record TX event
    recorder.record(
        direction="tx",
        raw_bytes=bytes([0xAA, 0x55, 0x01, 0x00]),
        command_name="ping",
        command_id=1,
        decoded_fields={"channel": 0},
        crc_valid=True,
        latency_ms=5.2,
    )

    # Record RX event
    recorder.record(
        direction="rx",
        raw_bytes=bytes([0xAA, 0x55, 0x81, 0x00]),
        command_name="pong",
        command_id=129,
        decoded_fields={"status": "OK"},
        crc_valid=True,
    )

    assert len(recorder.events) == 2

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Export JSONL
        jsonl_file = recorder.export_jsonl(tmp_path / "session.jsonl")
        assert jsonl_file.exists()
        lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert "ping" in lines[0]

        # 2. Export CSV
        csv_file = recorder.export_csv(tmp_path / "session.csv")
        assert csv_file.exists()
        csv_text = csv_file.read_text(encoding="utf-8")
        assert "timestamp,direction" in csv_text
        assert "TX" in csv_text

        # 3. Export RAW .bin
        bin_file = recorder.export_raw_bin(tmp_path / "session.bin")
        assert bin_file.exists()
        raw_bytes = bin_file.read_bytes()
        assert raw_bytes.startswith(bytes([0xAA, 0x55]))
