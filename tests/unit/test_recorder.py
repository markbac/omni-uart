"""Unit tests for SessionRecorder and export engines (JSONL, CSV, RAW .bin, PCAPNG)."""

import tempfile
from pathlib import Path

from omniuart.core.recorder import SessionRecorder


def test_session_recorder_and_exporters() -> None:
    """Verify recording packet events and exporting to JSONL, CSV, RAW .bin, and PCAPNG formats."""
    recorder = SessionRecorder()
    assert len(recorder.events) == 0

    # Record TX event with command_id 0 to verify falsy 0 preservation
    ev1 = recorder.record(
        direction="tx",
        raw_bytes=bytes([0xAA, 0x55, 0x00, 0x00]),
        command_name="zero_cmd",
        command_id=0,
        decoded_fields={"channel": 0},
        crc_valid=True,
        latency_ms=5.2,
    )
    assert ev1 is not None

    # Record RX event
    ev2 = recorder.record(
        direction="rx",
        raw_bytes=bytes([0xAA, 0x55, 0x81, 0x00]),
        command_name="pong",
        command_id=129,
        decoded_fields={"status": "OK"},
        crc_valid=True,
    )
    assert ev2 is not None

    assert len(recorder.events) == 2

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Export JSONL
        jsonl_file = recorder.export_jsonl(tmp_path / "session.jsonl")
        assert jsonl_file.exists()
        lines = jsonl_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert "zero_cmd" in lines[0]

        # 2. Export CSV and verify command_id 0 is preserved
        csv_file = recorder.export_csv(tmp_path / "session.csv")
        assert csv_file.exists()
        csv_text = csv_file.read_text(encoding="utf-8")
        assert "timestamp,direction" in csv_text
        assert "TX" in csv_text
        assert ",0," in csv_text  # command_id 0 preserved

        # 3. Export RAW .bin
        bin_file = recorder.export_raw_bin(tmp_path / "session.bin")
        assert bin_file.exists()
        raw_bytes = bin_file.read_bytes()
        assert raw_bytes.startswith(bytes([0xAA, 0x55]))

        # 4. Export PCAPNG
        pcapng_file = recorder.export_pcapng(tmp_path / "session.pcapng")
        assert pcapng_file.exists()
        pcap_data = pcapng_file.read_bytes()
        assert pcap_data.startswith(b"\x0a\x0d\x0d\x0a")  # SHB magic


def test_recorder_stop_resume_and_ring_buffer() -> None:
    """Verify recorder stop, start, and capacity eviction."""
    recorder = SessionRecorder(max_capacity=3)

    for i in range(5):
        recorder.record(direction="tx", raw_bytes=bytes([i]))

    assert len(recorder.events) == 3

    recorder.stop()
    res = recorder.record(direction="tx", raw_bytes=b"\x99")
    assert res is None
    assert len(recorder.events) == 3

    recorder.start()
    res2 = recorder.record(direction="rx", raw_bytes=b"\x88")
    assert res2 is not None
    assert len(recorder.events) == 3
