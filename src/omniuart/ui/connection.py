"""Connection state for the web API: one real (or explicitly simulated) link shared by all requests."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from omniuart.core.recorder import SessionRecorder
from omniuart.core.session import DeviceSession
from omniuart.core.models import ProtocolSpec
from omniuart.core.transport import AsyncTransport, HardwareSerialTransport, VirtualTransport

VIRTUAL_PORT = "virtual"


class NotConnectedError(RuntimeError):
    """Raised when a request needs a link but none has been opened."""


class ConnectionManager:
    """Owns the transport opened by ``/api/serial/connect`` and hands out sessions bound to it.

    A real port keeps one transport open across requests. The ``virtual`` port is an explicit,
    labelled simulation: each request gets a fresh simulated device for the protocol in use, and
    every API response says ``"simulated": true``.
    """

    def __init__(self) -> None:
        self.transport: Optional[AsyncTransport] = None
        self.virtual = False
        self.port: Optional[str] = None
        self.baudrate = 115200
        self.rts = True
        self.dtr = True
        self.lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self.virtual or (self.transport is not None and self.transport.is_open)

    def state(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "port": self.port,
            "baudrate": self.baudrate,
            "rts": self.rts,
            "dtr": self.dtr,
            "simulated": self.virtual,
        }

    async def connect(self, port: str, baudrate: int, rts: bool, dtr: bool) -> None:
        """Open ``port`` (replacing any open link). Raises on failure and leaves the manager disconnected."""
        await self.disconnect()
        if port == VIRTUAL_PORT:
            self.virtual = True
        else:
            transport = HardwareSerialTransport(port, baudrate=baudrate)
            await transport.open()  # raises if the port does not exist or cannot be opened
            try:
                await transport.set_pin_state("rts", rts)
                await transport.set_pin_state("dtr", dtr)
            except Exception:  # noqa: BLE001 - not every port or URL handler supports modem lines
                pass
            self.transport = transport
        self.port, self.baudrate, self.rts, self.dtr = port, baudrate, rts, dtr

    async def disconnect(self) -> None:
        if self.transport is not None:
            try:
                await self.transport.close()
            finally:
                self.transport = None
        self.virtual = False
        self.port = None

    def session(self, spec: ProtocolSpec, recorder: Optional[SessionRecorder] = None) -> DeviceSession:
        """A session for ``spec`` on the current link."""
        if self.virtual:
            return DeviceSession(spec, VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0), recorder=recorder)
        if self.transport is None or not self.transport.is_open:
            raise NotConnectedError("No serial connection. Connect a port first (POST /api/serial/connect).")
        return DeviceSession(spec, self.transport, recorder=recorder)

    @asynccontextmanager
    async def use(self, spec: ProtocolSpec, recorder: Optional[SessionRecorder] = None) -> AsyncIterator[DeviceSession]:
        """Exclusive use of the link for one request; the shared transport is left open afterwards."""
        session = self.session(spec, recorder)
        async with self.lock:
            if self.virtual:
                await session.open()
            try:
                yield session
            finally:
                if self.virtual:
                    await session.close()
