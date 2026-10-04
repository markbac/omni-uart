"""Validation and Golden-Vector Tests for Wireshark PCAPNG Exporter (#212).

Serial Traffic Representation:
- LinkType: USER0 (147) in Interface Description Block (IDB)
- Enhanced Packet Block (EPB) block type: 0x00000006
- EPB Flags option (type 2, len 4): 0x00000001 (Inbound/RX), 0x00000002 (Outbound/TX)
- Timestamps: 64-bit microsecond resolution
- Alignment: 32-bit (4-byte) payload padding
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path
import pytest
from omniuart.core.recorder import SessionRecorder


def parse_pcapng_blocks(pcap_bytes: bytes):
    """Parse and validate PCAPNG binary block structure."""
    pos = 0
    blocks = []
    while pos < len(pcap_bytes):
        assert pos + 8 <= len(pcap_bytes), "Truncated block header"
        block_type, block_len = struct.unpack("<II", pcap_bytes[pos : pos + 8])
        assert block_len >= 12, f"Invalid block length {block_len}"
        assert pos + block_len <= len(pcap_bytes), f"Block length {block_len} exceeds total bytes"

        # Trailing block length must match header length
        trailer_len = struct.unpack("<I", pcap_bytes[pos + block_len - 4 : pos + block_len])[0]
        assert block_len == trailer_len, f"Block length mismatch: header {block_len} != trailer {trailer_len}"

        block_body = pcap_bytes[pos + 8 : pos + block_len - 4]
        blocks.append((block_type, block_len, block_body))
        pos += block_len

    return blocks


def test_pcapng_golden_vector_structure(tmp_path: Path) -> None:
    recorder = SessionRecorder()
    recorder.record("tx", b"\xAA\x55\x01\x00\x01\x00\x12\x34", command_name="ping")
    recorder.record("rx", b"\xAA\x55\x02\x00\x81\x00\x56\x78", command_name="ping_ack")

    target = tmp_path / "golden_capture.pcapng"
    res_path = recorder.export_pcapng(target)

    pcap_data = target.read_bytes()
    blocks = parse_pcapng_blocks(pcap_data)

    # Must contain at least SHB (0x0A0D0D0A), IDB (0x00000001), and 2 EPBs (0x00000006)
    assert len(blocks) == 4

    # 1. SHB
    shb_type, shb_len, shb_body = blocks[0]
    assert shb_type == 0x0A0D0D0A
    assert shb_len == 28
    magic = struct.unpack("<I", shb_body[0:4])[0]
    assert magic == 0x1A2B3C4D

    # 2. IDB
    idb_type, idb_len, idb_body = blocks[1]
    assert idb_type == 0x00000001
    assert idb_len == 20
    link_type = struct.unpack("<H", idb_body[0:2])[0]
    assert link_type == 147  # LINKTYPE_USER0

    # 3. EPB TX
    epb1_type, epb1_len, epb1_body = blocks[2]
    assert epb1_type == 0x00000006
    iface_id, ts_hi, ts_lo, cap_len, orig_len = struct.unpack("<IIIII", epb1_body[0:20])
    assert orig_len == 8
    # Direction option at end of EPB body: option type 2 (flags), len 4, value 2 (TX)
    assert epb1_body[-12:-4] == struct.pack("<HHI", 2, 4, 2)

    # 4. EPB RX
    epb2_type, epb2_len, epb2_body = blocks[3]
    assert epb2_type == 0x00000006
    iface_id2, ts_hi2, ts_lo2, cap_len2, orig_len2 = struct.unpack("<IIIII", epb2_body[0:20])
    assert orig_len2 == 8
    # Direction option at end of EPB body: option type 2 (flags), len 4, value 1 (RX)
    assert epb2_body[-12:-4] == struct.pack("<HHI", 2, 4, 1)


@pytest.mark.skipif(shutil.which("tshark") is None, reason="tshark not installed in PATH")
def test_pcapng_external_tshark_validation(tmp_path: Path) -> None:
    recorder = SessionRecorder()
    recorder.record("tx", b"\xAA\x55\x01\x00\x01\x00\x12\x34", command_name="ping")
    recorder.record("rx", b"\xAA\x55\x02\x00\x81\x00\x56\x78", command_name="ping_ack")

    target = tmp_path / "tshark_capture.pcapng"
    recorder.export_pcapng(target)

    # Validate file readability with tshark
    proc = subprocess.run(["tshark", "-r", str(target)], capture_output=True, text=True)
    assert proc.returncode == 0
