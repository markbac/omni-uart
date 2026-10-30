"""Run a file transfer over a device session, using a declarative transfer definition (#244-#248, #251).

:class:`~omniuart.core.transfer.TransferManager` is protocol independent: it chunks the file and tracks
state, progress, retries and history. This module drives it over a real link: the start, chunk, ack,
commit and abort phases are protocol commands named by a
:class:`~omniuart.core.device_ui.TransferProtocolSpec`, so every acknowledgement and the commit come
from the device, never from the host merely having written bytes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from omniuart.core.codec import CodecError
from omniuart.core.device_ui import TransferProtocolSpec
from omniuart.core.models import CommandSpec, ProtocolSpec
from omniuart.core.session import Exchange, SerialSession
from omniuart.core.transfer import TransferChunk, TransferManager, TransferMetadata, TransferProgress, TransferState


class TransferDefinitionError(ValueError):
    """The transfer definition does not fit the protocol (a command or parameter is missing)."""


def transfer_commands(spec: ProtocolSpec, definition: TransferProtocolSpec) -> Dict[str, CommandSpec]:
    """Phase -> command for every configured phase. Raises :class:`TransferDefinitionError` for a missing command."""
    resolved: Dict[str, CommandSpec] = {}
    for phase, name in definition.commands().items():
        cmd = spec.get_command(name)
        if cmd is None:
            raise TransferDefinitionError(f"transfer {phase} command '{name}' is not in protocol '{spec.metadata.name}'")
        resolved[phase] = cmd
    data_param = definition.params.get("data")
    if not any(p.name == data_param for p in resolved["chunk"].parameters):
        raise TransferDefinitionError(f"chunk command '{resolved['chunk'].name}' has no '{data_param}' parameter for the chunk data")
    return resolved


@dataclass
class TransferOutcome:
    """How a transfer ended. ``committed`` is true only when the device accepted the commit command."""

    state: TransferState
    committed: bool
    progress: TransferProgress
    error: Optional[str] = None


class SessionTransfer:
    """Upload one file to a device over an open session."""

    def __init__(self, spec: ProtocolSpec, definition: TransferProtocolSpec, manager: Optional[TransferManager] = None) -> None:
        self.spec = spec
        self.definition = definition
        self.commands = transfer_commands(spec, definition)
        self.manager = manager or TransferManager()
        self._cancel = asyncio.Event()

    @property
    def progress(self) -> TransferProgress:
        return self.manager.progress

    def cancel(self) -> None:
        """Ask a running upload to stop before its next chunk; the device is sent the abort command."""
        self._cancel.set()

    def _params(self, cmd: CommandSpec, values: Dict[str, Any]) -> Dict[str, Any]:
        """Map logical values onto the parameters ``cmd`` actually has."""
        names = {p.name for p in cmd.parameters}
        out: Dict[str, Any] = {}
        for logical, value in values.items():
            param = self.definition.params.get(logical)
            if param in names:
                out[param] = value
        return out

    async def _send(self, session: SerialSession, phase: str, values: Dict[str, Any]) -> Exchange:
        cmd = self.commands[phase]
        return await session.send(cmd, self._params(cmd, values))

    async def upload(
        self,
        session: SerialSession,
        file_name: str,
        data: bytes,
        file_type: str = "binary",
        version: Optional[str] = None,
        on_progress: Optional[Callable[[TransferProgress], None]] = None,
    ) -> TransferOutcome:
        """Start, send every chunk with acknowledgement and retries, then commit. Never raises for device failures."""
        manager = self.manager
        meta = TransferMetadata(file_name=file_name, total_size=len(data), file_type=file_type, version=version)
        chunk_size = min(self.definition.default_chunk_size, self.definition.max_chunk_size)
        manager.capabilities.max_chunk_size = self.definition.max_chunk_size
        manager.capabilities.min_chunk_size = min(manager.capabilities.min_chunk_size, chunk_size)
        ok, err = manager.prepare_upload(meta, data, chunk_size=chunk_size, window_size=1)
        if not ok:
            return TransferOutcome(TransferState.FAILED, False, manager.progress, err)
        assert manager._window_controller is not None
        manager._window_controller.max_retries = self.definition.retries

        def report() -> None:
            if on_progress:
                on_progress(manager.progress)

        common = {"file_name": file_name, "file_type": file_type, "total_size": len(data), "checksum": meta.expected_checksum, "chunk_size": chunk_size}
        try:
            if "start" in self.commands:
                started = await self._send(session, "start", common)
                if not started.ok:
                    return self._fail(f"device refused the transfer: {started.error}", report)
            manager.start_transfer()
            report()

            while manager.state is TransferState.TRANSFERRING:
                if self._cancel.is_set():
                    await self._abort(session)
                    manager.cancel()
                    report()
                    return TransferOutcome(TransferState.CANCELLED, False, manager.progress, "cancelled")
                chunks: List[TransferChunk] = manager.get_next_chunks()
                if not chunks:
                    break
                for chunk in chunks:
                    if await self._send_chunk(session, chunk):
                        manager.acknowledge_chunk(chunk.sequence_number)
                    else:
                        can_retry, _ = manager.handle_chunk_timeout(chunk.sequence_number)
                        if not can_retry:
                            await self._abort(session)
                            report()
                            return TransferOutcome(TransferState.FAILED, False, manager.progress, manager.progress.error_message)
                    report()

            if "commit" not in self.commands:
                manager.verify_and_commit()  # host-side checksum only; the device never confirmed anything
                report()
                return TransferOutcome(manager.state, False, manager.progress, None)

            committed = await self._send(session, "commit", common)
            if not committed.ok:
                await self._abort(session)
                return self._fail(f"device rejected the commit: {committed.error}", report)
            result = manager.commit()
            report()
            return TransferOutcome(manager.state, result.success, manager.progress, result.error)
        except CodecError as exc:
            return self._fail(f"transfer command could not be encoded: {exc}", report)

    async def _send_chunk(self, session: SerialSession, chunk: TransferChunk) -> bool:
        values = {
            "sequence": chunk.sequence_number,
            "offset": chunk.offset,
            "data": chunk.data,
            "chunk_crc32": chunk.crc32,
            "is_last": chunk.is_last,
        }
        sent = await self._send(session, "chunk", values)
        if not sent.ok:
            return False
        if "ack" in self.commands:
            return (await self._send(session, "ack", values)).ok
        return True

    async def _abort(self, session: SerialSession) -> None:
        if "abort" in self.commands:
            try:
                await self._send(session, "abort", {})
            except CodecError:
                pass  # the abort itself is best effort; the transfer is already failing

    def _fail(self, message: str, report: Callable[[], None]) -> TransferOutcome:
        self.manager.abort(message)
        report()
        return TransferOutcome(TransferState.FAILED, False, self.manager.progress, message)
