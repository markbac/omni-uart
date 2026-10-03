"""Thread-safe device controller for GUI clients.

A GUI thread cannot await, so :class:`BackgroundDevice` runs one asyncio loop in a worker thread and
exposes the shared session layer (connect, send, run a script) as methods returning
:class:`concurrent.futures.Future`. Operations are serialised, so a poll can never interleave with a
script on the same link. It contains no GUI code and can be tested headlessly.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future
from typing import Any, Awaitable, Callable, Mapping, Optional, TypeVar

from omniuart.core.models import CommandSpec, ProtocolSpec, ScriptSpec, SerialConfig
from omniuart.core.runner import ScriptResult, ScriptRunner, StepResult
from omniuart.core.session import DeviceSession, Exchange, read_available
from omniuart.core.transport import AsyncTransport, HardwareSerialTransport, VirtualTransport

T = TypeVar("T")

VIRTUAL_PORT = "virtual"


class NotConnected(RuntimeError):
    """An operation needs an open link but none has been opened."""


def is_safe_poll_command(cmd: CommandSpec) -> bool:
    """Whether ``cmd`` may be sent repeatedly without operator input.

    Only commands tagged ``dashboard`` (read-only status queries) that expect a response and whose
    parameters all have defaults qualify; nothing that could actuate hardware is ever polled.
    """
    if "dashboard" not in cmd.tags or cmd.response is None:
        return False
    return all(p.default is not None for p in cmd.parameters)


class BackgroundDevice:
    """One link (a real serial port or the labelled virtual device) driven from a worker thread."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._lock: Optional[asyncio.Lock] = None
        self._transport: Optional[AsyncTransport] = None
        self._virtual = False
        self._port: Optional[str] = None
        self._start_guard = threading.Lock()

    # ------------------------------------------------------------------ state
    @property
    def connected(self) -> bool:
        return self._virtual or (self._transport is not None and self._transport.is_open)

    @property
    def simulated(self) -> bool:
        return self._virtual

    @property
    def port(self) -> Optional[str]:
        return self._port

    # ------------------------------------------------------------------ loop plumbing
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._start_guard:
            if self._loop is None:
                ready = threading.Event()

                def run() -> None:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self._loop = loop
                    self._lock = asyncio.Lock()
                    ready.set()
                    loop.run_forever()
                    loop.close()

                self._thread = threading.Thread(target=run, name="omniuart-device", daemon=True)
                self._thread.start()
                ready.wait()
            assert self._loop is not None
            return self._loop

    def _submit(self, coro: Awaitable[T]) -> "Future[T]":
        return asyncio.run_coroutine_threadsafe(coro, self._ensure_loop())  # type: ignore[arg-type]

    # ------------------------------------------------------------------ connection
    def connect(
        self,
        port: str,
        baudrate: int,
        serial_config: Optional[SerialConfig] = None,
        rts: bool = True,
        dtr: bool = True,
    ) -> "Future[None]":
        """Open ``port`` (or the virtual device when ``port == 'virtual'``). The future raises on failure."""
        return self._submit(self._connect(port, baudrate, serial_config, rts, dtr))

    async def _connect(self, port: str, baudrate: int, serial_config: Optional[SerialConfig], rts: bool, dtr: bool) -> None:
        assert self._lock is not None
        async with self._lock:
            await self._disconnect()
            if port == VIRTUAL_PORT:
                self._virtual = True
            else:
                transport = HardwareSerialTransport(port, baudrate=baudrate, serial_config=serial_config)
                await transport.open()  # raises when the port is missing or busy
                try:
                    await transport.set_pin_state("rts", rts)
                    await transport.set_pin_state("dtr", dtr)
                except Exception:  # noqa: BLE001 - not every port supports modem lines
                    pass
                self._transport = transport
            self._port = port

    def disconnect(self) -> "Future[None]":
        return self._submit(self._locked_disconnect())

    async def _locked_disconnect(self) -> None:
        assert self._lock is not None
        async with self._lock:
            await self._disconnect()

    async def _disconnect(self) -> None:
        transport, self._transport = self._transport, None
        self._virtual = False
        self._port = None
        if transport is not None:
            await transport.close()

    def close(self) -> None:
        """Close the link and stop the worker thread."""
        if self._loop is None:
            return
        try:
            self.disconnect().result(timeout=5)
        except Exception:  # noqa: BLE001 - shutting down regardless
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None

    # ------------------------------------------------------------------ operations
    def _session(self, spec: ProtocolSpec) -> DeviceSession:
        if self._virtual:
            return DeviceSession(spec, VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0))
        if self._transport is None or not self._transport.is_open:
            raise NotConnected("Not connected. Connect a serial port or the virtual device first.")
        return DeviceSession(spec, self._transport)

    async def _with_session(self, spec: ProtocolSpec, work: Callable[[DeviceSession], Awaitable[T]]) -> T:
        assert self._lock is not None
        async with self._lock:
            session = self._session(spec)
            if self._virtual:
                await session.open()
            try:
                return await work(session)
            finally:
                if self._virtual:
                    await session.close()

    def send(
        self,
        spec: ProtocolSpec,
        command: str,
        params: Optional[Mapping[str, Any]] = None,
        timeout_ms: Optional[int] = None,
    ) -> "Future[Exchange]":
        """Encode and transmit ``command``. Invalid parameters raise ``CodecError`` before anything is sent."""
        return self._submit(self._with_session(spec, lambda s: s.send(command, params, timeout_ms=timeout_ms)))

    def run_script(
        self,
        script: ScriptSpec,
        spec: ProtocolSpec,
        on_step: Optional[Callable[[StepResult], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> "Future[ScriptResult]":
        """Run ``script`` with the shared runner. Cancel the future to stop it."""

        async def work(session: DeviceSession) -> ScriptResult:
            return await ScriptRunner(script, session, on_step=on_step, on_log=on_log).run()

        return self._submit(self._with_session(spec, work))

    def send_raw(self, data: bytes, spec: Optional[ProtocolSpec] = None, timeout_ms: int = 300) -> "Future[bytes]":
        """Write ``data`` as-is and return whatever the device sends back (empty on silence).

        The virtual device answers per protocol, so ``spec`` is required when it is the active link.
        """

        async def work() -> bytes:
            assert self._lock is not None
            async with self._lock:
                if self._virtual:
                    if spec is None:
                        raise NotConnected("The virtual device needs an active protocol to answer raw bytes.")
                    transport: AsyncTransport = VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0)
                    await transport.open()
                    try:
                        await transport.write(data)
                        return await read_available(transport, timeout_ms)
                    finally:
                        await transport.close()
                if self._transport is None or not self._transport.is_open:
                    raise NotConnected("Not connected. Connect a serial port or the virtual device first.")
                await self._transport.write(data)
                return await read_available(self._transport, timeout_ms)

        return self._submit(work())
