"""Deterministic integration tests for transfer simulation and fault injection fixtures (#252)."""

from __future__ import annotations

import hashlib
import pytest
from omniuart.core.transfer import (
    CommitPolicy,
    FileType,
    TransferManager,
    TransferMetadata,
    TransferSimulationConfig,
    TransferSimulator,
    TransferState,
)


@pytest.mark.asyncio
async def test_transfer_simulation_successful(transfer_simulator: TransferSimulator) -> None:
    """Verify end-to-end successful transfer simulation (#252)."""
    payload = b"OmniUART firmware payload 0123456789" * 20  # 720 bytes
    meta = TransferMetadata(
        file_name="firmware.bin",
        total_size=len(payload),
        file_type=FileType.FIRMWARE.value,
        expected_checksum=hashlib.sha256(payload).hexdigest(),
    )

    manager = TransferManager()
    ok = await manager.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=transfer_simulator.handle_chunk,
        chunk_size=128,
        window_size=2,
    )

    assert ok is True
    assert manager.state in (TransferState.VERIFYING, TransferState.COMPLETED)
    assert transfer_simulator.get_reassembled_data() == payload
    assert transfer_simulator.verify(meta.expected_checksum) is True

    commit_res = transfer_simulator.commit()
    assert commit_res.success is True
    assert transfer_simulator.committed is True


@pytest.mark.asyncio
async def test_transfer_simulation_delayed_acks() -> None:
    """Verify transfer handles delayed acknowledgements (#252)."""
    config = TransferSimulationConfig(ack_delay_ms=2.0)
    sim = TransferSimulator(config=config)

    payload = b"Delayed Ack Test Data" * 10
    meta = TransferMetadata(
        file_name="config.json",
        total_size=len(payload),
        file_type=FileType.CONFIGURATION.value,
        expected_checksum=hashlib.sha256(payload).hexdigest(),
    )

    manager = TransferManager()
    ok = await manager.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=sim.handle_chunk,
        chunk_size=64,
    )

    assert ok is True
    assert sim.get_reassembled_data() == payload


@pytest.mark.asyncio
async def test_transfer_simulation_lost_chunks() -> None:
    """Verify dropped chunks trigger retry and eventual recovery (#252)."""
    # Drop chunk 1 on first attempt
    config = TransferSimulationConfig(drop_chunks={1}, max_retries_per_chunk=1)
    sim = TransferSimulator(config=config)

    payload = b"Chunk Loss Recovery Test" * 15
    meta = TransferMetadata(
        file_name="telemetry.log",
        total_size=len(payload),
        file_type=FileType.LOG.value,
        expected_checksum=hashlib.sha256(payload).hexdigest(),
    )

    manager = TransferManager()
    ok = await manager.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=sim.handle_chunk,
        chunk_size=64,
    )

    assert ok is True
    assert manager.progress.retries_count >= 1
    assert sim.get_reassembled_data() == payload


@pytest.mark.asyncio
async def test_transfer_simulation_duplicated_chunks() -> None:
    """Verify duplicate chunks are absorbed idempotently (#252)."""
    config = TransferSimulationConfig(duplicate_chunks={0, 2})
    sim = TransferSimulator(config=config)

    payload = b"Duplicate Chunk Absorption Test" * 10
    meta = TransferMetadata(
        file_name="cert.pem",
        total_size=len(payload),
        file_type=FileType.CERTIFICATE.value,
        expected_checksum=hashlib.sha256(payload).hexdigest(),
    )

    manager = TransferManager()
    ok = await manager.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=sim.handle_chunk,
        chunk_size=64,
    )

    assert ok is True
    assert sim.reassembler.duplicate_count >= 2
    assert sim.get_reassembled_data() == payload


@pytest.mark.asyncio
async def test_transfer_simulation_corrupted_chunks() -> None:
    """Verify corrupted chunks are rejected by CRC check and retransmitted (#252)."""
    config = TransferSimulationConfig(corrupt_chunks={0}, max_retries_per_chunk=1)
    sim = TransferSimulator(config=config)

    payload = b"Corrupted Chunk Recovery" * 10
    meta = TransferMetadata(
        file_name="payload.bin",
        total_size=len(payload),
        file_type=FileType.BINARY.value,
        expected_checksum=hashlib.sha256(payload).hexdigest(),
    )

    manager = TransferManager()
    ok = await manager.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=sim.handle_chunk,
        chunk_size=64,
    )

    assert ok is True
    assert manager.progress.retries_count >= 1


@pytest.mark.asyncio
async def test_transfer_simulation_interrupted_and_checkpoint_resumed() -> None:
    """Verify interrupted transfer can save checkpoint and resume (#247, #252)."""
    config = TransferSimulationConfig(interrupt_after_chunk=2)
    sim = TransferSimulator(config=config)

    payload = b"Interrupted and Resumed Transfer Test Data" * 20  # ~840 bytes
    meta = TransferMetadata(
        file_name="large_fw.bin",
        total_size=len(payload),
        file_type=FileType.FIRMWARE.value,
        expected_checksum=hashlib.sha256(payload).hexdigest(),
    )

    manager1 = TransferManager()
    # First attempt interrupted after chunk 2
    ok1 = await manager1.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=sim.handle_chunk,
        chunk_size=128,
    )
    assert ok1 is False
    assert sim.interrupted is True

    # Save checkpoint from partial transfer
    checkpoint = manager1.create_checkpoint()
    assert checkpoint is not None
    assert len(checkpoint.acknowledged_chunks) >= 2

    # Second simulator allowing full transfer
    sim2 = TransferSimulator()
    manager2 = TransferManager()
    ok2, err = manager2.resume_from_checkpoint(checkpoint, payload)
    assert ok2 is True

    # Complete remaining transfer
    ok_resumed = await manager2.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=sim2.handle_chunk,
        chunk_size=128,
    )
    assert ok_resumed is True


@pytest.mark.asyncio
async def test_transfer_simulation_failed_verification() -> None:
    """Verify simulation of device verification failure (#252)."""
    config = TransferSimulationConfig(fail_verification=True)
    sim = TransferSimulator(config=config)

    payload = b"Verification Failure Test"
    meta = TransferMetadata(
        file_name="test.bin",
        total_size=len(payload),
        file_type=FileType.BINARY.value,
        expected_checksum=hashlib.sha256(payload).hexdigest(),
    )

    manager = TransferManager()
    await manager.transfer_blob_async(
        metadata=meta,
        data=payload,
        chunk_sender=sim.handle_chunk,
    )

    assert sim.verify(meta.expected_checksum) is False


@pytest.mark.asyncio
async def test_transfer_simulation_rejected_commit() -> None:
    """Verify simulation of rejected commit and rollback (#248, #252)."""
    config = TransferSimulationConfig(reject_commit=True)
    sim = TransferSimulator(config=config)

    commit_res = sim.commit(policy=CommitPolicy.ATOMIC_WITH_ROLLBACK)
    assert commit_res.success is False
    assert commit_res.rolled_back is True
    assert "rejected" in str(commit_res.error).lower() or "error" in str(commit_res.error).lower()
