"""Unit tests for the generic file and blob transfer subsystem (#244, #245, #246, #243)."""

from __future__ import annotations

import asyncio
import hashlib
from typing import List

import pytest
from omniuart.core.transfer import (
    ChecksumAlgorithm,
    ChunkingEngine,
    FileType,
    SlidingWindowController,
    TransferCapabilities,
    TransferChunk,
    TransferManager,
    TransferMetadata,
    TransferProgress,
    TransferReassembler,
    TransferState,
)


def test_capabilities_validation() -> None:
    """Verify transfer capabilities reject oversized or unsupported files."""
    caps = TransferCapabilities(max_file_size=1024, supported_types=["firmware", "configuration"])

    # Valid
    ok, err = caps.validate_file("firmware.bin", "firmware", 512)
    assert ok is True
    assert err is None

    # Oversized
    ok, err = caps.validate_file("huge.bin", "firmware", 2048)
    assert ok is False
    assert "exceeds" in str(err)

    # Unsupported type
    ok, err = caps.validate_file("key.pem", "certificate", 256)
    assert ok is False
    assert "not supported" in str(err)

    # Empty file
    ok, err = caps.validate_file("empty.bin", "firmware", 0)
    assert ok is False


def test_chunking_engine_basic_and_boundaries() -> None:
    """Verify chunking engine slices data correctly with CRC32 and SHA256."""
    data = b"Hello, OmniUART Chunking Engine!" * 20  # 640 bytes
    chunks = ChunkingEngine.chunk_data(data, chunk_size=128)

    assert len(chunks) == 5
    assert chunks[0].sequence_number == 0
    assert chunks[0].offset == 0
    assert chunks[0].size == 128
    assert chunks[0].is_last is False
    assert chunks[0].verify_chunk_crc()

    assert chunks[-1].sequence_number == 4
    assert chunks[-1].offset == 128 * 4
    assert chunks[-1].size == len(data) - (128 * 4)
    assert chunks[-1].is_last is True
    assert chunks[-1].verify_chunk_crc()

    # Recombine
    reassembled = b"".join(c.data for c in chunks)
    assert reassembled == data


def test_chunking_empty_data() -> None:
    """Verify chunking engine handles 0-byte payload."""
    chunks = ChunkingEngine.chunk_data(b"", chunk_size=256)
    assert len(chunks) == 1
    assert chunks[0].size == 0
    assert chunks[0].is_last is True


def test_reassembler_in_order_and_out_of_order() -> None:
    """Verify reassembler reconstructs out-of-order chunks and ignores duplicates."""
    payload = b"ABCDEFGHIJ" * 50  # 500 bytes
    chunks = ChunkingEngine.chunk_data(payload, chunk_size=100)
    assert len(chunks) == 5

    reassembler = TransferReassembler(total_size=len(payload), expected_chunks=5)
    assert reassembler.is_complete() is False

    # Feed out of order: 2, 0, 4, 1, 3
    for idx in [2, 0, 4, 1]:
        ok, err = reassembler.add_chunk(chunks[idx])
        assert ok is True
        assert err is None
        assert reassembler.is_complete() is False

    # Check missing
    assert reassembler.missing_sequences() == [3]

    # Duplicate addition
    ok, _ = reassembler.add_chunk(chunks[2])
    assert ok is True
    assert reassembler.duplicate_count == 1

    # Corrupt chunk rejection
    bad_chunk = TransferChunk(sequence_number=3, offset=300, size=100, data=b"x" * 100, crc32=0x12345678)
    ok, err = reassembler.add_chunk(bad_chunk)
    assert ok is False
    assert "CRC mismatch" in str(err)
    assert reassembler.corrupt_count == 1

    # Add real chunk 3
    ok, err = reassembler.add_chunk(chunks[3])
    assert ok is True
    assert reassembler.is_complete() is True

    result = reassembler.reassemble()
    assert result == payload


def test_sliding_window_controller() -> None:
    """Verify sliding window flow control, ack advancement, and retransmissions."""
    data = b"0123456789" * 10  # 100 bytes
    chunks = ChunkingEngine.chunk_data(data, chunk_size=10)
    assert len(chunks) == 10

    # Window of 3
    controller = SlidingWindowController(chunks, window_size=3, max_retries=2)

    # Window eligible: 0, 1, 2
    batch1 = controller.get_in_flight_available()
    assert [c.sequence_number for c in batch1] == [0, 1, 2]
    assert controller.get_in_flight_available() == []

    # Ack chunk 0 -> window slides to allow chunk 3
    controller.acknowledge(0)
    assert controller.base == 1
    batch2 = controller.get_in_flight_available()
    assert [c.sequence_number for c in batch2] == [3]

    # Ack chunk 2 (out of order ack) -> base stays at 1
    controller.acknowledge(2)
    assert controller.base == 1

    # Ack chunk 1 -> base slides past both 1 and 2 to 3!
    controller.acknowledge(1)
    assert controller.base == 3

    # Timeout handling
    can_retry, chunk = controller.mark_timeout(3)
    assert can_retry is True
    assert chunk is not None and chunk.retries == 1

    # Exceed max retries
    controller.mark_timeout(3)
    can_retry, _ = controller.mark_timeout(3)
    assert can_retry is False


def test_transfer_manager_upload_lifecycle() -> None:
    """Verify complete upload lifecycle from prepare through verify and commit."""
    mgr = TransferManager()
    data = b"OmniUART firmware payload v2.0" * 30  # 900 bytes
    meta = TransferMetadata(
        file_name="firmware_update.bin",
        total_size=len(data),
        file_type=FileType.FIRMWARE.value,
        checksum_algo=ChecksumAlgorithm.SHA256.value,
    )

    ok, err = mgr.prepare_upload(meta, data, chunk_size=200, window_size=2)
    assert ok is True
    assert err is None
    assert mgr.state == TransferState.PREPARING

    assert mgr.start_transfer() is True
    assert mgr.state == TransferState.TRANSFERRING

    # Transmit and acknowledge all chunks
    while mgr.state == TransferState.TRANSFERRING:
        batch = mgr.get_next_chunks()
        if not batch:
            break
        for c in batch:
            mgr.acknowledge_chunk(c.sequence_number)

    assert mgr.state == TransferState.VERIFYING
    assert mgr.progress.percent_complete == 100.0

    # Commit
    assert mgr.verify_and_commit() is True
    assert mgr.state == TransferState.COMPLETED

    # Check history record
    history = mgr.history.get_records()
    assert len(history) == 1
    assert history[0].file_name == "firmware_update.bin"
    assert history[0].status == TransferState.COMPLETED
    assert history[0].total_size == len(data)


def test_transfer_manager_cancellation_and_abort() -> None:
    """Verify user cancellation and abort transition states and record in history."""
    mgr = TransferManager()
    data = b"test config blob" * 10
    meta = TransferMetadata(file_name="config.json", total_size=len(data), file_type=FileType.CONFIGURATION.value)

    mgr.prepare_upload(meta, data, chunk_size=32)
    mgr.start_transfer()
    assert mgr.state == TransferState.TRANSFERRING

    # Cancel
    mgr.cancel("User aborted from UI")
    assert mgr.state == TransferState.CANCELLED
    assert mgr.progress.state == TransferState.CANCELLED

    records = mgr.history.get_records()
    assert len(records) == 1
    assert records[0].status == TransferState.CANCELLED
    assert "User aborted" in str(records[0].error)


def test_transfer_manager_download_lifecycle() -> None:
    """Verify download transfer reassembly and checksum verification."""
    data = b"Extracted log buffer from MCU flash" * 20
    expected_hash = hashlib.sha256(data).hexdigest()

    mgr = TransferManager()
    meta = TransferMetadata(
        file_name="crashdump.log",
        total_size=len(data),
        file_type=FileType.LOG.value,
        checksum_algo=ChecksumAlgorithm.SHA256.value,
        expected_checksum=expected_hash,
    )

    ok, err = mgr.prepare_download(meta)
    assert ok is True
    assert mgr.state == TransferState.TRANSFERRING

    chunks = ChunkingEngine.chunk_data(data, chunk_size=128)
    for c in chunks:
        ok, err = mgr.receive_chunk(c)
        assert ok is True

    assert mgr.state == TransferState.VERIFYING

    success, assembled, err = mgr.finish_download()
    assert success is True
    assert assembled == data
    assert mgr.state == TransferState.COMPLETED


@pytest.mark.asyncio
async def test_transfer_blob_async_simulation() -> None:
    """Verify async transfer loop with mock transmission channel."""
    mgr = TransferManager()
    payload = b"ASYNC BLOB DATA FOR TEST" * 50
    meta = TransferMetadata(
        file_name="cert.pem",
        total_size=len(payload),
        file_type=FileType.CERTIFICATE.value,
    )

    progress_reports: List[TransferProgress] = []

    def on_progress(p: TransferProgress) -> None:
        progress_reports.append(p)

    async def mock_channel(chunk: TransferChunk) -> bool:
        await asyncio.sleep(0.001)
        return True

    success = await mgr.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=mock_channel,
        chunk_size=100,
        window_size=2,
        on_progress=on_progress,
    )

    assert success is True
    assert mgr.state == TransferState.COMPLETED
    assert len(progress_reports) > 0
    assert progress_reports[-1].percent_complete == 100.0
