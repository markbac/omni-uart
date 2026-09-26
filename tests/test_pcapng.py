"""Tests for Wireshark PCAPNG stream exporter."""

from __future__ import annotations

import struct
from pathlib import Path
from omniuart.core.recorder import SessionRecorder


def test_export_pcapng_file_generation(tmp_path: Path) -> None:
    recorder = SessionRecorder()
    recorder.record("tx", b"\xAA\x55\x01\x00\x01\x00\x12\x34", command_name="ping")
    recorder.record("rx", b"\xAA\x55\x02\x00\x81\x00\x56\x78", command_name="ping_ack")

    target = tmp_path / "capture.pcapng"
    res_path = recorder.export_pcapng(target)

    assert res_path.exists()
    assert res_path.stat().st_size > 0

    # Read binary header magic
    header_bytes = target.read_bytes()
    shb_magic = struct.unpack("<I", header_bytes[0:4])[0]
    assert shb_magic == 0x0A0D0D0A
