"""Server-side state behind the device dashboard (#230, #233, #234, #246, #318).

One :class:`DeviceConsole` per protocol keeps the live device state, the Engineer view's recent
exchanges and running transfers. Every exchange made on the web API's shared link is recorded here,
so the dashboard shows only values the device actually sent.
"""

from __future__ import annotations

import asyncio
import itertools
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from omniuart.core.codec import DecodedFrame
from omniuart.core.device_state import LiveDeviceState
from omniuart.core.engineer_view import EngineerProtocolView, ProtocolExchangeDetail
from omniuart.core.models import ProtocolSpec
from omniuart.core.session import Exchange
from omniuart.core.transfer import TransferProgress, TransferState
from omniuart.core.transfer_session import SessionTransfer, TransferOutcome

MAX_EXCHANGES = 200
_JOB_IDS = itertools.count(1)


@dataclass
class TransferJob:
    """A transfer started from the dashboard and running in the background."""

    job_id: str
    widget_ref: str
    file_name: str
    transfer: SessionTransfer
    task: Optional["asyncio.Task[TransferOutcome]"] = None
    outcome: Optional[TransferOutcome] = None
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        progress: TransferProgress = self.outcome.progress if self.outcome else self.transfer.progress
        done = self.outcome is not None
        return {
            "job_id": self.job_id,
            "widget_ref": self.widget_ref,
            "file_name": self.file_name,
            "done": done,
            "committed": bool(self.outcome and self.outcome.committed),
            "state": (self.outcome.state if done and self.outcome else progress.state).value,
            "error": self.outcome.error if self.outcome else None,
            "progress": progress.to_dict(),
        }


class DeviceConsole:
    """Live state, recent traffic and transfers for one protocol."""

    def __init__(self, spec: ProtocolSpec) -> None:
        self.spec = spec
        self.state = LiveDeviceState(device_id=spec.metadata.name)
        self.engineer = EngineerProtocolView(spec)
        self._order: Deque[str] = deque()
        self.transfers: Dict[str, TransferJob] = {}

    def record(self, exchange: Exchange) -> ProtocolExchangeDetail:
        """Store an exchange for the Engineer view and update state from its response and any unsolicited frames."""
        detail = self.engineer.inspect_exchange(exchange, exchange_id=f"ex{next(_JOB_IDS)}")
        self._order.append(detail.exchange_id)
        while len(self._order) > MAX_EXCHANGES:
            self.engineer.exchanges.pop(self._order.popleft(), None)
        if exchange.ok and exchange.response is not None:
            self._update(exchange.response, exchange.command)
        for frame in exchange.unsolicited:
            self._update(frame, frame.name or "unsolicited")
        return detail

    def _update(self, frame: DecodedFrame, namespace: str) -> None:
        if frame.ok and frame.fields:
            for name, value in frame.fields.items():
                self.state.update_field(name, value, namespace=namespace)

    def connection_lost(self) -> None:
        self.state.mark_connection_lost()

    def recent_exchanges(self, limit: int = 50) -> List[Dict[str, Any]]:
        ids = list(self._order)[-limit:]
        return [self.engineer.exchanges[i].to_dict() for i in reversed(ids) if i in self.engineer.exchanges]

    def snapshot(self, limit: int = 50) -> Dict[str, Any]:
        return {
            "state": self.state.get_state_snapshot(),
            "exchanges": self.recent_exchanges(limit),
            "transfers": [job.to_dict() for job in self.transfers.values()],
        }

    def add_transfer(self, widget_ref: str, file_name: str, transfer: SessionTransfer) -> TransferJob:
        job = TransferJob(job_id=f"t{next(_JOB_IDS)}", widget_ref=widget_ref, file_name=file_name, transfer=transfer)
        self.transfers[job.job_id] = job
        return job

    def active_transfer(self) -> Optional[TransferJob]:
        return next((j for j in self.transfers.values() if j.outcome is None), None)


class ConsoleRegistry:
    """One console per protocol name."""

    def __init__(self) -> None:
        self._consoles: Dict[str, DeviceConsole] = {}

    def get(self, spec: ProtocolSpec) -> DeviceConsole:
        console = self._consoles.get(spec.metadata.name)
        if console is None:
            console = self._consoles[spec.metadata.name] = DeviceConsole(spec)
        return console

    def connection_lost(self) -> None:
        for console in self._consoles.values():
            console.connection_lost()

    def clear(self) -> None:
        self._consoles.clear()


__all__ = ["ConsoleRegistry", "DeviceConsole", "TransferJob", "TransferState"]
