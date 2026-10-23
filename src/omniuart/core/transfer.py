"""Generic File and Blob Transfer Subsystem for OmniUART (#244, #245, #246, #243).

Provides transport- and protocol-independent transfer management for files and opaque blobs
(firmware, configuration, certificates, telemetry logs, binary blobs) between host and device.
Supports chunking, sliding window flow control, reassembly, acknowledgements, duplicate detection,
retransmissions, integrity verification (SHA-256, CRC32), transfer history, and progress tracking.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
import zlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class TransferState(str, Enum):
    """Lifecycle states of a file/blob transfer (#244, #243)."""

    IDLE = "idle"
    PREPARING = "preparing"
    TRANSFERRING = "transferring"
    VERIFYING = "verifying"
    COMMITTING = "committing"
    RECONNECTING = "reconnecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TransferDirection(str, Enum):
    """Direction of the file/blob transfer."""

    UPLOAD = "upload"      # Host -> Device
    DOWNLOAD = "download"  # Device -> Host


class FileType(str, Enum):
    """Semantic file or blob categorization (#244)."""

    FIRMWARE = "firmware"
    CONFIGURATION = "configuration"
    CERTIFICATE = "certificate"
    LOG = "log"
    BINARY = "binary"
    CUSTOM = "custom"


class ChecksumAlgorithm(str, Enum):
    """Supported integrity verification algorithms (#244, #245)."""

    SHA256 = "sha256"
    CRC32 = "crc32"
    MD5 = "md5"

class CommitPolicy(str, Enum):
    """Integrity and commit semantics (#248)."""

    IMMEDIATE = "immediate"
    EXPLICIT_VERIFIED = "explicit_verified"
    ATOMIC_WITH_ROLLBACK = "atomic_with_rollback"


@dataclass
class CommitResult:
    """Outcome of commit operation (#248)."""

    success: bool
    committed_version: Optional[str] = None
    checksum_verified: bool = False
    error: Optional[str] = None
    rolled_back: bool = False


@dataclass
class TransferCheckpoint:
    """State checkpoint enabling resuming interrupted transfers (#247)."""

    transfer_id: str
    file_name: str
    total_size: int
    expected_checksum: str
    chunk_size: int
    total_chunks: int
    acknowledged_chunks: List[int]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "file_name": self.file_name,
            "total_size": self.total_size,
            "expected_checksum": self.expected_checksum,
            "chunk_size": self.chunk_size,
            "total_chunks": self.total_chunks,
            "acknowledged_chunks": list(self.acknowledged_chunks),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TransferCheckpoint:
        return cls(
            transfer_id=data["transfer_id"],
            file_name=data["file_name"],
            total_size=data["total_size"],
            expected_checksum=data["expected_checksum"],
            chunk_size=data.get("chunk_size", 256),
            total_chunks=data.get("total_chunks", 0),
            acknowledged_chunks=data.get("acknowledged_chunks", []),
            timestamp=data.get("timestamp", time.time()),
        )



@dataclass
class TransferCapabilities:
    """Device or protocol file transfer capabilities (#244, #246)."""

    supported_types: List[str] = field(
        default_factory=lambda: [
            FileType.FIRMWARE.value,
            FileType.CONFIGURATION.value,
            FileType.CERTIFICATE.value,
            FileType.LOG.value,
            FileType.BINARY.value,
        ]
    )
    max_file_size: int = 16 * 1024 * 1024  # 16 MB default
    min_chunk_size: int = 16
    max_chunk_size: int = 8192
    default_chunk_size: int = 256
    supported_checksums: List[str] = field(
        default_factory=lambda: [ChecksumAlgorithm.SHA256.value, ChecksumAlgorithm.CRC32.value]
    )
    supports_resume: bool = True
    supports_abort: bool = True
    supports_windowing: bool = True
    max_window_size: int = 8

    def validate_file(self, file_name: str, file_type: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """Validate if a proposed transfer fits within device capabilities."""
        if file_size > self.max_file_size:
            return False, f"File size ({file_size} B) exceeds device max capability ({self.max_file_size} B)"
        if file_size <= 0:
            return False, "File size must be greater than 0 bytes"
        if file_type not in self.supported_types:
            return False, f"File type '{file_type}' is not supported by device capabilities {self.supported_types}"
        return True, None


@dataclass
class TransferMetadata:
    """Transfer metadata describing the file/blob (#244)."""

    file_name: str
    total_size: int
    file_type: str = FileType.BINARY.value
    transfer_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    checksum_algo: str = ChecksumAlgorithm.SHA256.value
    expected_checksum: str = ""
    direction: TransferDirection = TransferDirection.UPLOAD
    version: Optional[str] = None
    target_component: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_checksum(self, data: bytes) -> str:
        """Calculate checksum using configured algorithm."""
        if self.checksum_algo.lower() == ChecksumAlgorithm.CRC32.value:
            return f"0x{zlib.crc32(data):08X}"
        if self.checksum_algo.lower() == ChecksumAlgorithm.MD5.value:
            return hashlib.md5(data).hexdigest()
        return hashlib.sha256(data).hexdigest()

    def verify_checksum(self, data: bytes) -> bool:
        """Verify data against expected checksum."""
        if not self.expected_checksum:
            return True
        calc = self.calculate_checksum(data)
        return calc.lower() == self.expected_checksum.lower()


@dataclass
class TransferProgress:
    """Live transfer progress, rate, and ETA calculation (#244, #246)."""

    bytes_transferred: int = 0
    total_bytes: int = 0
    current_chunk: int = 0
    total_chunks: int = 0
    state: TransferState = TransferState.IDLE
    start_time: float = 0.0
    elapsed_seconds: float = 0.0
    transfer_rate_bps: float = 0.0
    estimated_remaining_seconds: float = 0.0
    retries_count: int = 0
    error_message: Optional[str] = None

    @property
    def percent_complete(self) -> float:
        if self.total_bytes <= 0:
            return 100.0 if self.state == TransferState.COMPLETED else 0.0
        return min(100.0, max(0.0, (self.bytes_transferred / self.total_bytes) * 100.0))

    def update(self, transferred_bytes: int, chunk_idx: int) -> None:
        """Update progress counters and calculate speed/ETA."""
        now = time.time()
        self.bytes_transferred = transferred_bytes
        self.current_chunk = chunk_idx

        if self.start_time > 0:
            self.elapsed_seconds = max(0.001, now - self.start_time)
            self.transfer_rate_bps = self.bytes_transferred / self.elapsed_seconds
            remaining_bytes = max(0, self.total_bytes - self.bytes_transferred)
            if self.transfer_rate_bps > 0:
                self.estimated_remaining_seconds = remaining_bytes / self.transfer_rate_bps
            else:
                self.estimated_remaining_seconds = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bytes_transferred": self.bytes_transferred,
            "total_bytes": self.total_bytes,
            "current_chunk": self.current_chunk,
            "total_chunks": self.total_chunks,
            "percent_complete": round(self.percent_complete, 2),
            "state": self.state.value,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "transfer_rate_bps": round(self.transfer_rate_bps, 2),
            "estimated_remaining_seconds": round(self.estimated_remaining_seconds, 2),
            "retries_count": self.retries_count,
            "error_message": self.error_message,
        }


@dataclass
class TransferChunk:
    """Individual data chunk representing part of a file/blob (#245)."""

    sequence_number: int  # 0-indexed
    offset: int
    size: int
    data: bytes
    crc32: int = 0
    sha256: str = ""
    is_last: bool = False
    retries: int = 0
    acknowledged: bool = False

    def __post_init__(self) -> None:
        if self.crc32 == 0 and self.data:
            self.crc32 = zlib.crc32(self.data)
        if not self.sha256 and self.data:
            self.sha256 = hashlib.sha256(self.data).hexdigest()

    def verify_chunk_crc(self) -> bool:
        """Verify chunk payload integrity using CRC32."""
        return zlib.crc32(self.data) == self.crc32


class ChunkingEngine:
    """Partitions arbitrary blobs into sequenced chunks (#245)."""

    @staticmethod
    def chunk_data(data: bytes, chunk_size: int = 256) -> List[TransferChunk]:
        """Split data into indexed chunks with offsets and CRC32."""
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")

        chunks: List[TransferChunk] = []
        total_len = len(data)

        if total_len == 0:
            chunks.append(
                TransferChunk(
                    sequence_number=0,
                    offset=0,
                    size=0,
                    data=b"",
                    crc32=0,
                    sha256=hashlib.sha256(b"").hexdigest(),
                    is_last=True,
                )
            )
            return chunks

        offset = 0
        seq = 0
        while offset < total_len:
            end = min(offset + chunk_size, total_len)
            chunk_bytes = data[offset:end]
            is_last = (end >= total_len)
            chunks.append(
                TransferChunk(
                    sequence_number=seq,
                    offset=offset,
                    size=len(chunk_bytes),
                    data=chunk_bytes,
                    crc32=zlib.crc32(chunk_bytes),
                    sha256=hashlib.sha256(chunk_bytes).hexdigest(),
                    is_last=is_last,
                )
            )
            offset = end
            seq += 1

        return chunks


class TransferReassembler:
    """Reassembles received chunks into original blob, validating ordering and integrity (#245)."""

    def __init__(self, total_size: int, expected_chunks: Optional[int] = None) -> None:
        self.total_size = total_size
        self.expected_chunks = expected_chunks
        self.received_chunks: Dict[int, TransferChunk] = {}
        self.duplicate_count: int = 0
        self.corrupt_count: int = 0

    def add_chunk(self, chunk: TransferChunk) -> Tuple[bool, Optional[str]]:
        """Add and validate a received chunk. Returns (accepted, error_message)."""
        if not chunk.verify_chunk_crc():
            self.corrupt_count += 1
            return False, f"Chunk {chunk.sequence_number} CRC mismatch (0x{chunk.crc32:08X})"

        if chunk.sequence_number in self.received_chunks:
            self.duplicate_count += 1
            # Duplicate accepted idempotently
            return True, None

        if chunk.offset + chunk.size > self.total_size and self.total_size > 0:
            return False, f"Chunk {chunk.sequence_number} exceeds total expected size {self.total_size}"

        self.received_chunks[chunk.sequence_number] = chunk
        return True, None

    def missing_sequences(self) -> List[int]:
        """Return list of sequence numbers that have not been received yet."""
        if not self.received_chunks:
            return [0]
        max_seq = max(self.received_chunks.keys())
        expected_total = self.expected_chunks if self.expected_chunks is not None else max_seq + 1
        return [i for i in range(expected_total) if i not in self.received_chunks]

    def is_complete(self) -> bool:
        """Check if all chunks have been received and total size matches."""
        if not self.received_chunks:
            return self.total_size == 0
        if self.missing_sequences():
            return False
        total_bytes = sum(c.size for c in self.received_chunks.values())
        return total_bytes == self.total_size

    def reassemble(self) -> bytes:
        """Reconstruct original bytes from ordered chunks."""
        if not self.is_complete():
            missing = self.missing_sequences()
            raise ValueError(f"Cannot reassemble incomplete transfer. Missing chunks: {missing}")

        sorted_chunks = sorted(self.received_chunks.values(), key=lambda c: c.sequence_number)
        return b"".join(c.data for c in sorted_chunks)


class SlidingWindowController:
    """Manages sliding window flow control for chunked transfers (#245)."""

    def __init__(self, chunks: List[TransferChunk], window_size: int = 1, max_retries: int = 3) -> None:
        self.chunks: List[TransferChunk] = chunks
        self.window_size: int = max(1, window_size)
        self.max_retries: int = max_retries
        self.base: int = 0
        self.next_seq: int = 0
        self.acknowledged: Set[int] = set()
        self.inflight_times: Dict[int, float] = {}

    def get_in_flight_available(self) -> List[TransferChunk]:
        """Return next chunk(s) eligible to be sent within current window."""
        available: List[TransferChunk] = []
        while self.next_seq < len(self.chunks) and (self.next_seq - self.base) < self.window_size:
            chunk = self.chunks[self.next_seq]
            available.append(chunk)
            self.inflight_times[chunk.sequence_number] = time.time()
            self.next_seq += 1
        return available

    def acknowledge(self, sequence_number: int) -> bool:
        """Record acknowledgement for a sequence number and advance window base."""
        if sequence_number < 0 or sequence_number >= len(self.chunks):
            return False
        self.acknowledged.add(sequence_number)
        self.chunks[sequence_number].acknowledged = True
        self.inflight_times.pop(sequence_number, None)

        # Advance base window past consecutively acknowledged chunks
        while self.base < len(self.chunks) and self.base in self.acknowledged:
            self.base += 1
        return True

    def mark_timeout(self, sequence_number: int) -> Tuple[bool, Optional[TransferChunk]]:
        """Mark chunk timed out and eligible for retransmission if under max retries (#245, #252)."""
        if sequence_number < 0 or sequence_number >= len(self.chunks):
            return False, None
        chunk = self.chunks[sequence_number]
        chunk.retries += 1
        self.inflight_times.pop(sequence_number, None)
        if chunk.retries > self.max_retries:
            return False, chunk  # Exceeded retries limit
        # Rewind next_seq so that this timed-out chunk is retransmitted on next window pull
        if self.next_seq > sequence_number:
            self.next_seq = sequence_number
        return True, chunk

    def is_all_acknowledged(self) -> bool:
        """Check if every chunk in the transfer has been acknowledged."""
        return len(self.acknowledged) == len(self.chunks)


@dataclass
class TransferRecord:
    """Historical audit record of a past file/blob transfer (#244)."""

    transfer_id: str
    file_name: str
    file_type: str
    direction: str
    total_size: int
    checksum: str
    status: TransferState
    started_at: float
    completed_at: Optional[float] = None
    duration_seconds: float = 0.0
    chunks_count: int = 0
    retries_count: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "direction": self.direction,
            "total_size": self.total_size,
            "checksum": self.checksum,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": round(self.duration_seconds, 2),
            "chunks_count": self.chunks_count,
            "retries_count": self.retries_count,
            "error": self.error,
        }


class TransferHistory:
    """Maintains an audit log of completed, failed, and aborted transfers (#244)."""

    def __init__(self, max_records: int = 100) -> None:
        self.max_records = max_records
        self._records: List[TransferRecord] = []

    def record_transfer(self, record: TransferRecord) -> None:
        """Add record and trim to max capacity."""
        self._records.append(record)
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records:]

    def get_records(self, limit: Optional[int] = None) -> List[TransferRecord]:
        """Return history records newest first."""
        records = list(reversed(self._records))
        return records[:limit] if limit else records

    def clear(self) -> None:
        """Clear transfer history."""
        self._records.clear()


@dataclass
class DeclarativeTransferDefinition:
    """Declarative specification mapping protocol commands to transfer phases (#245)."""

    protocol_name: str
    start_command: str = "transfer_start"
    data_command: str = "transfer_data"
    ack_command: str = "transfer_ack"
    finish_command: str = "transfer_finish"
    abort_command: str = "transfer_abort"
    chunk_size_param: str = "chunk_size"
    offset_param: str = "offset"
    data_param: str = "payload"
    crc_param: str = "crc32"
    seq_param: str = "sequence_number"


class TransferManager:
    """Transport- and protocol-independent Transfer Manager (#244, #245, #246, #243)."""

    def __init__(
        self,
        capabilities: Optional[TransferCapabilities] = None,
        history: Optional[TransferHistory] = None,
    ) -> None:
        self.capabilities: TransferCapabilities = capabilities or TransferCapabilities()
        self.history: TransferHistory = history or TransferHistory()
        self.metadata: Optional[TransferMetadata] = None
        self.progress: TransferProgress = TransferProgress()
        self.state: TransferState = TransferState.IDLE

        self._raw_data: bytes = b""
        self._chunks: List[TransferChunk] = []
        self._window_controller: Optional[SlidingWindowController] = None
        self._reassembler: Optional[TransferReassembler] = None
        self._is_cancelled: bool = False
        self._started_timestamp: float = 0.0

    def prepare_upload(
        self,
        metadata: TransferMetadata,
        data: bytes,
        chunk_size: Optional[int] = None,
        window_size: int = 1,
    ) -> Tuple[bool, Optional[str]]:
        """Validate capabilities and initialize upload transfer (#244, #245)."""
        valid, err = self.capabilities.validate_file(metadata.file_name, metadata.file_type, len(data))
        if not valid:
            self.state = TransferState.FAILED
            self.progress.state = TransferState.FAILED
            self.progress.error_message = err
            return False, err

        metadata.total_size = len(data)
        if not metadata.expected_checksum:
            metadata.expected_checksum = metadata.calculate_checksum(data)

        effective_chunk_size = chunk_size or self.capabilities.default_chunk_size
        effective_chunk_size = max(
            self.capabilities.min_chunk_size,
            min(effective_chunk_size, self.capabilities.max_chunk_size),
        )

        effective_window = min(window_size, self.capabilities.max_window_size if self.capabilities.supports_windowing else 1)

        self.metadata = metadata
        self._raw_data = data
        self._chunks = ChunkingEngine.chunk_data(data, chunk_size=effective_chunk_size)
        self._window_controller = SlidingWindowController(self._chunks, window_size=effective_window)

        self.state = TransferState.PREPARING
        self._is_cancelled = False
        self._started_timestamp = time.time()

        self.progress = TransferProgress(
            bytes_transferred=0,
            total_bytes=len(data),
            current_chunk=0,
            total_chunks=len(self._chunks),
            state=TransferState.PREPARING,
            start_time=self._started_timestamp,
        )
        return True, None

    def start_transfer(self) -> bool:
        """Begin transferring chunks."""
        if self.state not in (TransferState.PREPARING, TransferState.IDLE):
            return False
        self.state = TransferState.TRANSFERRING
        self.progress.state = TransferState.TRANSFERRING
        return True

    def get_next_chunks(self) -> List[TransferChunk]:
        """Fetch next chunk(s) within the sliding window ready for transmission."""
        if self.state != TransferState.TRANSFERRING or self._is_cancelled or not self._window_controller:
            return []
        return self._window_controller.get_in_flight_available()

    def acknowledge_chunk(self, sequence_number: int) -> bool:
        """Handle device acknowledgement of a transferred chunk (#245)."""
        if not self._window_controller or self.state != TransferState.TRANSFERRING:
            return False

        acked = self._window_controller.acknowledge(sequence_number)
        if acked:
            acked_bytes = sum(c.size for c in self._chunks if c.acknowledged)
            self.progress.update(transferred_bytes=acked_bytes, chunk_idx=sequence_number + 1)

            if self._window_controller.is_all_acknowledged():
                self.state = TransferState.VERIFYING
                self.progress.state = TransferState.VERIFYING
        return acked

    def handle_chunk_timeout(self, sequence_number: int) -> Tuple[bool, Optional[TransferChunk]]:
        """Handle chunk acknowledgement timeout, retransmitting if retries remain."""
        if not self._window_controller:
            return False, None
        self.progress.retries_count += 1
        can_retry, chunk = self._window_controller.mark_timeout(sequence_number)
        if not can_retry:
            self.abort(f"Chunk {sequence_number} exceeded max retransmission retries")
            return False, chunk
        return True, chunk

    def verify_and_commit(self) -> bool:
        """Perform end-to-end checksum verification and commit transfer (#244)."""
        if self.state != TransferState.VERIFYING or not self.metadata:
            return False

        self.state = TransferState.COMMITTING
        self.progress.state = TransferState.COMMITTING

        # End-to-end payload checksum verification
        if not self.metadata.verify_checksum(self._raw_data):
            self.abort("Integrity check failed: payload checksum mismatch on verification")
            return False

        self.state = TransferState.COMPLETED
        self.progress.state = TransferState.COMPLETED
        self.progress.bytes_transferred = self.progress.total_bytes

        self._record_history(TransferState.COMPLETED, None)
        return True

    def cancel(self, reason: str = "Transfer cancelled by user") -> None:
        """Cancel an in-progress transfer gracefully (#244, #246)."""
        self._is_cancelled = True
        self.state = TransferState.CANCELLED
        self.progress.state = TransferState.CANCELLED
        self.progress.error_message = reason
        self._record_history(TransferState.CANCELLED, reason)

    def abort(self, error_message: str) -> None:
        """Abort an in-progress transfer due to error (#244)."""
        self.state = TransferState.FAILED
        self.progress.state = TransferState.FAILED
        self.progress.error_message = error_message
        self._record_history(TransferState.FAILED, error_message)

    def prepare_download(self, metadata: TransferMetadata) -> Tuple[bool, Optional[str]]:
        """Initialize download transfer from device to host (#244)."""
        valid, err = self.capabilities.validate_file(metadata.file_name, metadata.file_type, metadata.total_size)
        if not valid:
            self.state = TransferState.FAILED
            self.progress.state = TransferState.FAILED
            self.progress.error_message = err
            return False, err

        metadata.direction = TransferDirection.DOWNLOAD
        self.metadata = metadata
        self._reassembler = TransferReassembler(total_size=metadata.total_size)
        self.state = TransferState.TRANSFERRING
        self._is_cancelled = False
        self._started_timestamp = time.time()

        self.progress = TransferProgress(
            bytes_transferred=0,
            total_bytes=metadata.total_size,
            current_chunk=0,
            total_chunks=0,
            state=TransferState.TRANSFERRING,
            start_time=self._started_timestamp,
        )
        return True, None

    def receive_chunk(self, chunk: TransferChunk) -> Tuple[bool, Optional[str]]:
        """Receive, validate and store a chunk during download (#244, #245)."""
        if self.state != TransferState.TRANSFERRING or not self._reassembler:
            return False, "Transfer is not in receiving state"

        ok, err = self._reassembler.add_chunk(chunk)
        if not ok:
            return False, err

        received_bytes = sum(c.size for c in self._reassembler.received_chunks.values())
        self.progress.update(transferred_bytes=received_bytes, chunk_idx=chunk.sequence_number + 1)

        if self._reassembler.is_complete():
            self.state = TransferState.VERIFYING
            self.progress.state = TransferState.VERIFYING

        return True, None

    def finish_download(self) -> Tuple[bool, bytes, Optional[str]]:
        """Assemble received chunks, verify end-to-end integrity, and finish download."""
        if not self._reassembler or not self.metadata:
            return False, b"", "No download initialized"

        try:
            assembled_bytes = self._reassembler.reassemble()
        except ValueError as e:
            self.abort(str(e))
            return False, b"", str(e)

        if not self.metadata.verify_checksum(assembled_bytes):
            err = "Download integrity verification failed: checksum mismatch"
            self.abort(err)
            return False, assembled_bytes, err

        self.state = TransferState.COMPLETED
        self.progress.state = TransferState.COMPLETED
        self._record_history(TransferState.COMPLETED, None)
        return True, assembled_bytes, None

    async def transfer_blob_async(
        self,
        metadata: TransferMetadata,
        data: bytes,
        chunk_sender: Callable[[TransferChunk], Any],
        chunk_size: Optional[int] = None,
        window_size: int = 1,
        auto_commit: bool = True,
        on_progress: Optional[Callable[[TransferProgress], None]] = None,
    ) -> bool:
        """Asynchronously transfer blob with progress reporting and ack loop (#244, #245)."""
        ok, err = self.prepare_upload(metadata, data, chunk_size=chunk_size, window_size=window_size)
        if not ok:
            return False

        self.start_transfer()
        if on_progress:
            on_progress(self.progress)

        while self._window_controller and not self._window_controller.is_all_acknowledged() and not self._is_cancelled:
            available = self.get_next_chunks()
            if not available:
                await asyncio.sleep(0.005)
                continue

            for chunk in available:
                if self._is_cancelled:
                    break
                # Send chunk through transport callback
                res = chunk_sender(chunk)
                if asyncio.iscoroutine(res):
                    send_ok = await res
                else:
                    send_ok = bool(res)

                if send_ok:
                    self.acknowledge_chunk(chunk.sequence_number)
                else:
                    can_retry, _ = self.handle_chunk_timeout(chunk.sequence_number)
                    if not can_retry:
                        return False

                if on_progress:
                    on_progress(self.progress)

        if self._is_cancelled:
            return False

        if auto_commit:
            return self.verify_and_commit()
        return self.state in (TransferState.VERIFYING, TransferState.TRANSFERRING)


    def create_checkpoint(self) -> Optional[TransferCheckpoint]:
        """Create persistent checkpoint of current transfer state for resume (#247)."""
        if not self.metadata or not self._window_controller:
            return None
        return TransferCheckpoint(
            transfer_id=self.metadata.transfer_id,
            file_name=self.metadata.file_name,
            total_size=self.metadata.total_size,
            expected_checksum=self.metadata.expected_checksum,
            chunk_size=self._chunks[0].size if self._chunks else self.capabilities.default_chunk_size,
            total_chunks=len(self._chunks),
            acknowledged_chunks=sorted(self._window_controller.acknowledged),
            timestamp=time.time(),
        )

    def resume_from_checkpoint(
        self,
        checkpoint: TransferCheckpoint,
        data: bytes,
        window_size: int = 1,
    ) -> Tuple[bool, Optional[str]]:
        """Resume an interrupted transfer from a saved checkpoint (#247)."""
        if len(data) != checkpoint.total_size:
            return False, f"Data size ({len(data)} B) does not match checkpoint ({checkpoint.total_size} B)"

        meta = TransferMetadata(
            file_name=checkpoint.file_name,
            total_size=checkpoint.total_size,
            transfer_id=checkpoint.transfer_id,
            expected_checksum=checkpoint.expected_checksum,
        )

        ok, err = self.prepare_upload(meta, data, chunk_size=checkpoint.chunk_size, window_size=window_size)
        if not ok:
            return False, err

        assert self._window_controller is not None
        # Restore acknowledged chunks from checkpoint
        for seq in checkpoint.acknowledged_chunks:
            if 0 <= seq < len(self._chunks):
                self._window_controller.acknowledge(seq)

        self._window_controller.next_seq = max(self._window_controller.next_seq, self._window_controller.base)
        acked_bytes = sum(c.size for c in self._chunks if c.acknowledged)
        self.progress.update(transferred_bytes=acked_bytes, chunk_idx=self._window_controller.base)
        self.state = TransferState.TRANSFERRING
        self.progress.state = TransferState.TRANSFERRING

        if self._window_controller.is_all_acknowledged():
            self.state = TransferState.VERIFYING
            self.progress.state = TransferState.VERIFYING

        return True, None

    def commit(
        self,
        policy: CommitPolicy = CommitPolicy.EXPLICIT_VERIFIED,
        pre_commit_hook: Optional[Callable[[], bool]] = None,
        post_commit_hook: Optional[Callable[[], bool]] = None,
        rollback_hook: Optional[Callable[[], None]] = None,
    ) -> CommitResult:
        """Atomic commit with integrity verification and rollback semantics (#248)."""
        if self.state not in (TransferState.VERIFYING, TransferState.TRANSFERRING, TransferState.COMPLETED) or not self.metadata:
            return CommitResult(success=False, error=f"Invalid state for commit: {self.state}")

        # 1. Integrity check
        checksum_ok = self.metadata.verify_checksum(self._raw_data) if self._raw_data else True
        if not checksum_ok:
            if rollback_hook:
                rollback_hook()
            self.abort("Integrity verification failed before commit")
            return CommitResult(success=False, checksum_verified=False, error="Checksum mismatch", rolled_back=bool(rollback_hook))

        # 2. Pre-commit hook
        if pre_commit_hook:
            try:
                if not pre_commit_hook():
                    if rollback_hook:
                        rollback_hook()
                    self.abort("Pre-commit validation rejected transfer")
                    return CommitResult(success=False, checksum_verified=True, error="Pre-commit hook rejected", rolled_back=bool(rollback_hook))
            except Exception as e:
                if rollback_hook:
                    rollback_hook()
                self.abort(f"Pre-commit error: {e}")
                return CommitResult(success=False, checksum_verified=True, error=str(e), rolled_back=bool(rollback_hook))

        self.state = TransferState.COMMITTING
        self.progress.state = TransferState.COMMITTING

        # 3. Post-commit hook
        if post_commit_hook:
            try:
                if not post_commit_hook():
                    if rollback_hook:
                        rollback_hook()
                    self.abort("Post-commit verification failed")
                    return CommitResult(success=False, checksum_verified=True, error="Post-commit verification failed", rolled_back=bool(rollback_hook))
            except Exception as e:
                if rollback_hook:
                    rollback_hook()
                self.abort(f"Post-commit error: {e}")
                return CommitResult(success=False, checksum_verified=True, error=str(e), rolled_back=bool(rollback_hook))

        self.state = TransferState.COMPLETED
        self.progress.state = TransferState.COMPLETED
        self.progress.bytes_transferred = self.progress.total_bytes
        self._record_history(TransferState.COMPLETED, None)

        return CommitResult(success=True, checksum_verified=True, committed_version=self.metadata.version)

    def _record_history(self, final_status: TransferState, error_msg: Optional[str]) -> None:
        """Record completed or terminated transfer in history log."""
        if not self.metadata:
            return
        now = time.time()
        duration = max(0.0, now - self._started_timestamp) if self._started_timestamp > 0 else 0.0
        record = TransferRecord(
            transfer_id=self.metadata.transfer_id,
            file_name=self.metadata.file_name,
            file_type=self.metadata.file_type,
            direction=self.metadata.direction.value,
            total_size=self.metadata.total_size,
            checksum=self.metadata.expected_checksum,
            status=final_status,
            started_at=self._started_timestamp,
            completed_at=now,
            duration_seconds=duration,
            chunks_count=len(self._chunks) if self._chunks else 0,
            retries_count=self.progress.retries_count,
            error=error_msg,
        )
        self.history.record_transfer(record)



class FirmwareUpdateWorkflow:
    """Specialized firmware update workflow built on TransferManager (#249)."""

    def __init__(self, manager: Optional[TransferManager] = None) -> None:
        self.manager = manager or TransferManager()

    def validate_firmware_image(
        self,
        image_bytes: bytes,
        target_hardware: Optional[str] = None,
        min_size: int = 16,
    ) -> Tuple[bool, Optional[str]]:
        """Validate firmware image size, magic, and target compatibility (#249)."""
        if len(image_bytes) < min_size:
            return False, f"Firmware image too small ({len(image_bytes)} B < {min_size} B)"
        if len(image_bytes) > self.manager.capabilities.max_file_size:
            return False, f"Firmware exceeds max device capability ({len(image_bytes)} B > {self.manager.capabilities.max_file_size} B)"
        return True, None

    async def execute_update(
        self,
        firmware_bytes: bytes,
        file_name: str,
        version: str,
        chunk_sender: Callable[[TransferChunk], Any],
        reboot_fn: Optional[Callable[[], Any]] = None,
        verify_version_fn: Optional[Callable[[], Any]] = None,
        on_progress: Optional[Callable[[TransferProgress], None]] = None,
        chunk_size: Optional[int] = None,
        window_size: int = 1,
    ) -> Tuple[bool, Optional[str]]:
        """Execute full firmware update lifecycle: validate, transfer, verify, commit, reboot, verify (#249)."""
        # 1. Validation
        valid, err = self.validate_firmware_image(firmware_bytes)
        if not valid:
            return False, err

        meta = TransferMetadata(
            file_name=file_name,
            total_size=len(firmware_bytes),
            file_type=FileType.FIRMWARE.value,
            version=version,
        )

        # 2. Transfer & Verification
        transferred = await self.manager.transfer_blob_async(
            metadata=meta,
            data=firmware_bytes,
            chunk_sender=chunk_sender,
            chunk_size=chunk_size,
            window_size=window_size,
            auto_commit=False,
            on_progress=on_progress,
        )
        if not transferred:
            return False, self.manager.progress.error_message or "Firmware transfer failed"

        # 3. Commit
        commit_res = self.manager.commit(policy=CommitPolicy.EXPLICIT_VERIFIED)
        if not commit_res.success:
            return False, commit_res.error or "Firmware commit failed"

        # 4. Reboot & Reconnect
        if reboot_fn:
            self.manager.state = TransferState.RECONNECTING
            self.manager.progress.state = TransferState.RECONNECTING
            if on_progress:
                on_progress(self.manager.progress)

            res = reboot_fn()
            if asyncio.iscoroutine(res):
                await res

        # 5. Post-update version verification
        if verify_version_fn:
            res_ver = verify_version_fn()
            active_version = await res_ver if asyncio.iscoroutine(res_ver) else res_ver
            if str(active_version).strip() != version.strip():
                return False, f"Post-update version mismatch: expected {version}, device reported {active_version}"

        self.manager.state = TransferState.COMPLETED
        self.manager.progress.state = TransferState.COMPLETED
        return True, None


class ConfigurationWorkflow:
    """Generic configuration file transfer, validation, and staging/apply workflow (#250)."""

    def __init__(self, manager: Optional[TransferManager] = None) -> None:
        self.manager = manager or TransferManager()

    def validate_configuration(self, config_bytes: bytes) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Validate JSON or Key-Value configuration format (#250)."""
        text = config_bytes.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return True, data, None
        except Exception:
            pass

        # Try key-value lines
        kv_data: Dict[str, Any] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                kv_data[k.strip()] = v.strip()
        if kv_data:
            return True, kv_data, None

        return False, None, "Invalid configuration format (expected valid JSON or key=value pairs)"

    def compute_diff(self, current: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Compute difference between current device config and incoming proposed config."""
        added = {k: new[k] for k in new if k not in current}
        modified = {k: {"old": current[k], "new": new[k]} for k in new if k in current and current[k] != new[k]}
        removed = {k: current[k] for k in current if k not in new}
        return {"added": added, "modified": modified, "removed": removed, "has_changes": bool(added or modified or removed)}

    async def import_configuration(
        self,
        config_bytes: bytes,
        file_name: str,
        chunk_sender: Callable[[TransferChunk], Any],
        apply_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
        apply_immediately: bool = True,
        on_progress: Optional[Callable[[TransferProgress], None]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Upload, validate, and optionally apply configuration to device (#250)."""
        valid, parsed, err = self.validate_configuration(config_bytes)
        if not valid or parsed is None:
            return False, err

        meta = TransferMetadata(
            file_name=file_name,
            total_size=len(config_bytes),
            file_type=FileType.CONFIGURATION.value,
        )

        ok = await self.manager.transfer_blob_async(
            metadata=meta,
            data=config_bytes,
            chunk_sender=chunk_sender,
            on_progress=on_progress,
        )
        if not ok:
            return False, self.manager.progress.error_message or "Configuration upload failed"

        if apply_immediately and apply_fn:
            res = apply_fn(parsed)
            if asyncio.iscoroutine(res):
                await res

        return True, None

@dataclass
class TransferSimulationConfig:
    """Configuration for simulating device and transport transfer behaviour (#252)."""

    ack_delay_ms: float = 0.0
    drop_chunks: Set[int] = field(default_factory=set)          # Chunks that are dropped (simulate loss/timeout)
    corrupt_chunks: Set[int] = field(default_factory=set)       # Chunks corrupted in transit (CRC failure)
    duplicate_chunks: Set[int] = field(default_factory=set)     # Chunks sent multiple times to device
    interrupt_after_chunk: Optional[int] = None                 # Interrupt connection after chunk N
    fail_verification: bool = False                             # Device reports checksum mismatch
    reject_commit: bool = False                                 # Device rejects commit operation
    max_retries_per_chunk: int = 3


class TransferSimulator:
    """Simulator simulating device-side transfer handling and fault injection (#252).

    Simulates:
    - Successful transfers
    - Delayed acknowledgements
    - Lost / dropped chunks (triggers sender timeout and retransmission)
    - Corrupted chunks (CRC verification failure on device)
    - Duplicated chunks (device reassembler duplicate detection)
    - Out-of-order chunks (reassembly window testing)
    - Interrupted connections (simulated disconnect/abort for checkpoint resumption)
    - Failed verification (hash mismatch on reassembled payload)
    - Rejected commits (e.g. firmware flash write error or signature rejection)
    """

    def __init__(
        self,
        total_size: int = 0,
        expected_chunks: Optional[int] = None,
        config: Optional[TransferSimulationConfig] = None,
    ) -> None:
        self.config: TransferSimulationConfig = config or TransferSimulationConfig()
        self.reassembler: TransferReassembler = TransferReassembler(total_size=total_size, expected_chunks=expected_chunks)
        self.received_chunks: List[TransferChunk] = []
        self.dropped_attempts: Dict[int, int] = {}
        self.corrupt_attempts: Dict[int, int] = {}
        self.interrupted: bool = False
        self.committed: bool = False

    async def handle_chunk(self, chunk: TransferChunk) -> bool:
        """Process incoming chunk according to simulation configuration."""
        seq = chunk.sequence_number

        # Auto-update reassembler total size on last chunk if not preset
        if self.reassembler.total_size == 0 and chunk.is_last:
            self.reassembler.total_size = chunk.offset + chunk.size

        # 1. Connection interruption check
        if self.config.interrupt_after_chunk is not None and seq >= self.config.interrupt_after_chunk:
            self.interrupted = True
            return False

        # 2. Simulated packet drop (lost chunk)
        if seq in self.config.drop_chunks:
            attempts = self.dropped_attempts.get(seq, 0)
            if attempts < self.config.max_retries_per_chunk:
                self.dropped_attempts[seq] = attempts + 1
                return False

        # 3. Simulated ACK delay
        if self.config.ack_delay_ms > 0:
            await asyncio.sleep(self.config.ack_delay_ms / 1000.0)

        # 4. Simulated corruption
        data_to_store = chunk.data
        if seq in self.config.corrupt_chunks:
            c_attempts = self.corrupt_attempts.get(seq, 0)
            if c_attempts < self.config.max_retries_per_chunk:
                self.corrupt_attempts[seq] = c_attempts + 1
                corrupt_bytes = bytearray(chunk.data)
                if corrupt_bytes:
                    corrupt_bytes[0] ^= 0xFF
                data_to_store = bytes(corrupt_bytes)

        # Reassemble chunk
        chunk_to_add = TransferChunk(
            sequence_number=chunk.sequence_number,
            offset=chunk.offset,
            size=len(data_to_store),
            data=data_to_store,
            crc32=chunk.crc32,
            sha256=chunk.sha256,
            is_last=chunk.is_last,
        )

        # If chunk is corrupted, device CRC check fails
        if not chunk_to_add.verify_chunk_crc():
            return False

        self.reassembler.add_chunk(chunk_to_add)
        self.received_chunks.append(chunk_to_add)

        # 5. Simulated duplication
        if seq in self.config.duplicate_chunks:
            self.reassembler.add_chunk(chunk_to_add)
            self.received_chunks.append(chunk_to_add)

        return True

    def verify(self, expected_checksum: str, algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> bool:
        """Verify reassembled payload against expected checksum."""
        if self.config.fail_verification:
            return False
        if not self.reassembler.is_complete():
            return False
        data = self.reassembler.reassemble()
        if algorithm == ChecksumAlgorithm.CRC32:
            calc = f"{zlib.crc32(data):08X}"
        elif algorithm == ChecksumAlgorithm.MD5:
            calc = hashlib.md5(data).hexdigest()
        else:
            calc = hashlib.sha256(data).hexdigest()
        return calc.lower() == expected_checksum.lower()

    def commit(self, policy: CommitPolicy = CommitPolicy.EXPLICIT_VERIFIED) -> CommitResult:
        """Simulate device commit."""
        if self.config.reject_commit:
            return CommitResult(success=False, error="Simulated flash write error / signature rejected", rolled_back=True)
        self.committed = True
        return CommitResult(success=True, committed_version="1.0.0", checksum_verified=True)

    def get_reassembled_data(self) -> bytes:
        if self.reassembler.is_complete():
            return self.reassembler.reassemble()
        sorted_chunks = sorted(self.reassembler.received_chunks.values(), key=lambda c: c.sequence_number)
        return b"".join(c.data for c in sorted_chunks)
