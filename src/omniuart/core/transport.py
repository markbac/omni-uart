"""Transport Abstraction Layer & Virtual MCU Simulator for OmniUART."""

from __future__ import annotations

import abc
import asyncio
import logging
import random
import time
from typing import Any, Callable, Dict, List, Optional

import serial
import serial.tools.list_ports

from omniuart.core.codec import FrameCodec, validate_fields
from omniuart.core.models import ProtocolSpec, SerialConfig

logger = logging.getLogger(__name__)


def list_available_ports() -> List[Dict[str, str]]:
    """Return a list of detected physical hardware serial ports."""
    ports_info = []
    for port in serial.tools.list_ports.comports():
        ports_info.append({
            "device": port.device,
            "description": port.description or "Serial Port",
            "hwid": port.hwid or "Unknown",
        })
    return ports_info


_READ_SLICE_S = 0.05
_PINS = ("dtr", "rts")


def _pin_key(pin: str) -> str:
    """Normalise a control-line name; every transport rejects the same unknown names."""
    key = str(pin).lower()
    if key not in _PINS:
        raise ValueError(f"Unsupported pin: {pin!r} (expected one of {', '.join(_PINS)})")
    return key


class AsyncTransport(abc.ABC):
    """Abstract Base Class for UART hardware and virtual transports."""

    @abc.abstractmethod
    async def open(self) -> None:
        """Open the transport interface."""
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        """Close the transport interface."""
        pass

    @abc.abstractmethod
    async def write(self, data: bytes) -> int:
        """Write raw bytes to the transport."""
        pass

    @abc.abstractmethod
    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        """Read up to ``size`` bytes, waiting at most ``timeout_ms`` in total.

        Contract shared by every transport: ``None`` waits until ``size`` bytes arrive, ``0`` is a
        non-blocking poll, and any other value is an absolute deadline (never multiplied by the
        number of chunks). On timeout the bytes that did arrive are returned, never discarded, and
        bytes beyond ``size`` stay buffered for the next read.
        """

    @property
    @abc.abstractmethod
    def is_open(self) -> bool:
        """Check if transport is currently connected and open."""
        pass

    @abc.abstractmethod
    async def set_pin_state(self, pin: str, state: bool) -> None:
        """Set DTR or RTS control pin state; unknown pin names raise ``ValueError`` on every transport."""
        _pin_key(pin)

    async def pulse_pins(self, pin_sequence: List[Dict[str, Any]]) -> None:
        """Pulse pin sequence, e.g. [{'pin': 'dtr', 'state': True, 'duration_ms': 100}]."""
        for step in pin_sequence:
            pin = str(step.get("pin", "")).lower()
            state = bool(step.get("state", True))
            duration = float(step.get("duration_ms", 10)) / 1000.0
            await self.set_pin_state(pin, state)
            if duration > 0:
                await asyncio.sleep(duration)


class VirtualTransport(AsyncTransport):
    """In-memory virtual MCU transport simulating hardware UART over async queues.

    Supports offline loopback, latency jitter, fault injection, and simulated DTR/RTS pins.
    """

    def __init__(
        self,
        protocol: Optional[ProtocolSpec] = None,
        latency_ms: float = 10.0,
        jitter_ms: float = 2.0,
        fault_crc_flip: bool = False,
        fault_drop_rate: float = 0.0,
        seed: Optional[int] = None,
        bit_flip_rate: float = 0.0,
        byte_noise_rate: float = 0.0,
        corrupt_crc_rate: float = 0.0,
        fragment_rate: float = 0.0,
        duplicate_rate: float = 0.0,
        truncate_rate: float = 0.0,
        rs485_rts_mode: bool = False,
        rs485_turnaround_ms: float = 0.0,
    ) -> None:
        self.protocol = protocol
        self.latency_ms = latency_ms
        self.jitter_ms = jitter_ms
        self.fault_crc_flip = fault_crc_flip
        self.fault_drop_rate = fault_drop_rate
        self.seed = seed
        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.bit_flip_rate = bit_flip_rate
        self.byte_noise_rate = byte_noise_rate
        self.corrupt_crc_rate = corrupt_crc_rate
        self.fragment_rate = fragment_rate
        self.duplicate_rate = duplicate_rate
        self.truncate_rate = truncate_rate
        self.rs485_rts_mode = rs485_rts_mode
        self.rs485_turnaround_ms = rs485_turnaround_ms
        self.line_errors: Dict[str, int] = {"break": 0, "framing": 0, "parity": 0}

        self._rx = _ReadBuffer()
        self._is_open = False
        self._rule_responses: Dict[int, bytes] = {}
        self.pin_states: Dict[str, bool] = {"dtr": False, "rts": False}

    async def open(self) -> None:
        """Connect virtual MCU transport."""
        self._is_open = True
        logger.info("Virtual MCU transport connected (loopback mode).")

    async def close(self) -> None:
        """Disconnect virtual MCU transport."""
        self._is_open = False
        logger.info("Virtual MCU transport disconnected.")

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def set_pin_state(self, pin: str, state: bool) -> None:
        """Set virtual DTR or RTS pin state."""
        self.pin_states[_pin_key(pin)] = state
        logger.info(f"Virtual pin '{pin.lower()}' set to {state}")

    def register_response(self, command_id: int, response_payload: bytes) -> None:
        """Register custom raw response bytes for a specific command ID."""
        self._rule_responses[command_id] = response_payload

    async def write(self, data: bytes) -> int:
        """Receive outbound bytes from host, process rules, and push response to RX queue."""
        if not self._is_open:
            raise RuntimeError("VirtualTransport is not open.")

        if self.rng.random() < self.fault_drop_rate:
            logger.warning("Fault injection: Dropped outbound frame.")
            return len(data)

        if self.rs485_rts_mode:
            await self.set_pin_state("rts", True)
            if self.rs485_turnaround_ms > 0:
                await asyncio.sleep(self.rs485_turnaround_ms / 1000.0)

        # Simulate transmission latency and jitter
        jitter = self.rng.uniform(-self.jitter_ms, self.jitter_ms) if self.jitter_ms > 0 else 0.0
        delay = max(0.001, (self.latency_ms + jitter) / 1000.0)
        await asyncio.sleep(delay)

        # Generate response byte frame
        resp_bytes = self._generate_response(data)

        if self.rs485_rts_mode:
            if self.rs485_turnaround_ms > 0:
                await asyncio.sleep(self.rs485_turnaround_ms / 1000.0)
            await self.set_pin_state("rts", False)

        if not resp_bytes:
            return len(data)

        buf = bytearray(resp_bytes)

        # 1. Corrupt CRC
        if (self.fault_crc_flip or self.rng.random() < self.corrupt_crc_rate) and len(buf) >= 2:
            buf[-1] ^= 0xFF

        # 2. Bit flips
        if self.bit_flip_rate > 0:
            for i in range(len(buf)):
                if self.rng.random() < self.bit_flip_rate:
                    buf[i] ^= (1 << self.rng.randint(0, 7))

        # 3. Byte noise
        if self.byte_noise_rate > 0:
            for i in range(len(buf)):
                if self.rng.random() < self.byte_noise_rate:
                    buf[i] = self.rng.randint(0, 255)

        # 4. Truncation
        if self.truncate_rate > 0 and len(buf) > 1 and self.rng.random() < self.truncate_rate:
            cutoff = self.rng.randint(1, len(buf) - 1)
            buf = buf[:cutoff]

        final_bytes = bytes(buf)

        # 5. Duplication
        if self.duplicate_rate > 0 and self.rng.random() < self.duplicate_rate:
            final_bytes = final_bytes + final_bytes

        # 6. Fragmentation
        if self.fragment_rate > 0 and len(final_bytes) > 2 and self.rng.random() < self.fragment_rate:
            mid = len(final_bytes) // 2
            self._rx.feed(final_bytes[:mid])
            await asyncio.sleep(0.005)
            self._rx.feed(final_bytes[mid:])
        else:
            self._rx.feed(final_bytes)

        return len(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        """Read up to ``size`` bytes; see :class:`_ReadBuffer` for timeout semantics."""
        if not self._is_open:
            raise RuntimeError("VirtualTransport is not open.")
        return await self._rx.read(size, timeout_ms, lambda: self._is_open)

    def _generate_response(self, request_bytes: bytes) -> bytes:
        """Simulate the device side of the link.

        With a protocol, the request is decoded by the protocol's codec and answered with the
        command's declared response (or a rule registered with :meth:`register_response`);
        frames that are invalid, unknown or have no response are not answered. Without a
        protocol the transport is a plain loopback and echoes the bytes back.
        """
        if self.protocol is None:
            return request_bytes

        codec = FrameCodec(self.protocol)
        frames, _ = codec.extract_frames(request_bytes, direction="request")
        out = bytearray()
        for frame in frames:
            if not frame.ok:
                continue
            if not codec.is_binary:
                out.extend(("OK" + codec.line_terminator()).encode("utf-8"))
                continue
            if frame.message_id in self._rule_responses:
                out.extend(self._rule_responses[frame.message_id])
                continue
            cmd = self.protocol.get_command(frame.name or "")
            if cmd is not None and validate_fields(cmd.parameters, frame.fields):
                continue
            if cmd is not None and cmd.response is not None:
                out.extend(codec.encode_response(cmd))
        return bytes(out)


class HardwareSerialTransport(AsyncTransport):
    """Physical serial hardware port transport using PySerial.

    ``port`` may be a device name (``COM3``, ``/dev/ttyUSB0``) or any PySerial URL handler such as
    ``loop://`` or ``socket://host:port``.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 1.0,
        serial_config: Optional[SerialConfig] = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_config = serial_config
        self._serial: Optional[serial.Serial] = None
        self._inflight: Optional["asyncio.Future[bytes]"] = None
        self._carry = bytearray()

    def _serial_kwargs(self) -> Dict[str, Any]:
        cfg = self.serial_config
        if cfg is None:
            return {}
        parity = {
            "none": serial.PARITY_NONE,
            "even": serial.PARITY_EVEN,
            "odd": serial.PARITY_ODD,
            "mark": serial.PARITY_MARK,
            "space": serial.PARITY_SPACE,
        }[cfg.parity.lower()]
        stopbits = {1.0: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2.0: serial.STOPBITS_TWO}[float(cfg.stopbits)]
        flow = cfg.flow_control.lower()
        return {
            "bytesize": cfg.bytesize,
            "parity": parity,
            "stopbits": stopbits,
            "rtscts": flow == "hardware",
            "xonxoff": flow == "software",
        }

    async def open(self) -> None:
        """Open physical serial port connection."""
        self._serial = await asyncio.to_thread(
            serial.serial_for_url, self.port, baudrate=self.baudrate, timeout=self.timeout, **self._serial_kwargs()
        )
        logger.info(f"Connected hardware serial port: {self.port} at {self.baudrate} bps")

    async def close(self) -> None:
        """Close physical serial port connection."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info(f"Closed hardware serial port: {self.port}")

    @property
    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def _write_and_flush(self, data: bytes) -> int:
        assert self._serial is not None
        written = self._serial.write(data)
        self._serial.flush()
        return written or 0

    async def write(self, data: bytes) -> int:
        if not self.is_open or not self._serial:
            raise RuntimeError("HardwareSerialTransport is not open.")
        return await asyncio.to_thread(self._write_and_flush, data)

    def _read_slice(self, size: int, seconds: float) -> bytes:
        serial_port = self._serial
        if serial_port is None or not serial_port.is_open:
            return b""
        serial_port.timeout = seconds
        return serial_port.read(size)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        """Read up to ``size`` bytes with the same timeout meaning as every transport.

        ``None`` waits forever, ``0`` polls, otherwise an absolute deadline applies. The blocking
        PySerial read is done in short slices so a cancelled caller never leaves a thread blocked
        for the whole timeout.
        """
        if not self.is_open or not self._serial:
            raise RuntimeError("HardwareSerialTransport is not open.")
        await self._harvest_inflight()
        deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000.0
        data = bytearray()
        while True:
            take = min(size - len(data), len(self._carry))
            if take:
                data.extend(self._carry[:take])
                del self._carry[:take]
            if len(data) >= size or not self.is_open:
                break
            if deadline is None:
                slice_s = _READ_SLICE_S
            else:
                slice_s = min(_READ_SLICE_S, max(0.0, deadline - time.monotonic()))
            self._inflight = asyncio.ensure_future(asyncio.to_thread(self._read_slice, size - len(data), slice_s))
            # If this caller is cancelled the slice still finishes; its bytes are kept for the next read.
            self._carry.extend(await asyncio.shield(self._inflight))
            self._inflight = None
            if deadline is not None and time.monotonic() >= deadline and not self._carry:
                break
        return bytes(data)

    async def _harvest_inflight(self) -> None:
        """Collect bytes read by a slice whose caller was cancelled."""
        pending, self._inflight = self._inflight, None
        if pending is not None:
            try:
                self._carry.extend(await pending)
            except Exception:  # noqa: BLE001 - port closed underneath the slice
                pass

    async def set_pin_state(self, pin: str, state: bool) -> None:
        if not self.is_open or not self._serial:
            raise RuntimeError("HardwareSerialTransport is not open.")
        pin_key = _pin_key(pin)
        if pin_key == "dtr":
            self._serial.dtr = state
        else:
            self._serial.rts = state


class PipeTransport(AsyncTransport):
    """Bidirectional in-memory pipe transport representing one endpoint of a virtual serial pair."""

    def __init__(self, port_name: str = "VIRTUAL_COM1") -> None:
        self.port_name = port_name
        self._rx = _ReadBuffer()
        self._peer: Optional[PipeTransport] = None
        self._is_open = False
        self.pin_states: Dict[str, bool] = {"dtr": False, "rts": False}

    def connect_peer(self, peer: PipeTransport) -> None:
        self._peer = peer

    async def open(self) -> None:
        self._is_open = True

    async def close(self) -> None:
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def write(self, data: bytes) -> int:
        if not self._is_open or not self._peer:
            raise RuntimeError("PipeTransport is not open or connected to peer.")
        self._peer._rx.feed(data)
        return len(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self._is_open:
            raise RuntimeError("PipeTransport is not open.")

        return await self._rx.read(size, timeout_ms, lambda: self._is_open)

    async def set_pin_state(self, pin: str, state: bool) -> None:
        self.pin_states[_pin_key(pin)] = state


class VirtualSerialPair:
    """Pair of linked virtual serial transports (host and device) for zero-hardware simulation."""

    def __init__(self, host_port: str = "COM_HOST", device_port: str = "COM_DEVICE") -> None:
        self.host = PipeTransport(port_name=host_port)
        self.device = PipeTransport(port_name=device_port)
        self.host.connect_peer(self.device)
        self.device.connect_peer(self.host)

    async def open(self) -> None:
        await self.host.open()
        await self.device.open()

    async def close(self) -> None:
        await self.host.close()
        await self.device.close()


class _ReadBuffer:
    """Byte buffer with timed reads, shared by the descriptor-based transports.

    ``read`` waits up to ``timeout_ms`` for ``size`` bytes and returns what has arrived (possibly
    nothing). ``None`` waits forever and ``0`` polls. After :meth:`set_eof` buffered bytes are still
    delivered and later reads return immediately.
    """

    def __init__(self) -> None:
        self._data = bytearray()
        self._event = asyncio.Event()
        self.eof = False

    def feed(self, chunk: bytes) -> None:
        self._data.extend(chunk)
        self._event.set()

    def set_eof(self) -> None:
        self.eof = True
        self._event.set()

    def wake(self) -> None:
        self._event.set()

    async def read(self, size: int, timeout_ms: Optional[int], is_open: Callable[[], bool]) -> bytes:
        deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000.0
        while len(self._data) < size and not self.eof and is_open():
            self._event.clear()
            if deadline is None:
                await self._event.wait()
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                await asyncio.wait_for(self._event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                break
        result = bytes(self._data[:size])
        del self._data[:size]
        return result


class PtyTransport(AsyncTransport):
    """Asynchronous transport over a POSIX pseudo-terminal file descriptor (Linux and macOS).

    Wrap an existing descriptor (``fd``) or open a pty slave device (``path``, for example the
    ``slave_pts_path`` of a :class:`PtySerialPair`). The descriptor is switched to raw,
    non-blocking mode and read through the event loop, so there is no line-discipline echo or
    newline translation and no worker threads.

    ``read`` waits up to ``timeout_ms`` for ``size`` bytes and returns whatever arrived (possibly
    nothing) when the time is up; ``timeout_ms=None`` waits forever and ``0`` polls. Once the other
    end has closed, buffered bytes are still delivered and later reads return ``b""`` at once;
    ``peer_closed`` reports it and writes raise :class:`ConnectionError`.
    """

    def __init__(self, fd: Optional[int] = None, path: Optional[str] = None, port_name: str = "PTY", owns_fd: bool = True) -> None:
        import os

        if os.name == "nt":
            raise NotImplementedError("PtyTransport is only supported on POSIX systems (Linux/macOS).")
        if (fd is None) == (path is None):
            raise ValueError("give exactly one of fd or path")
        self.port_name = path or port_name
        self._fd = fd
        self._path = path
        self._owns_fd = owns_fd or path is not None
        self._rx = _ReadBuffer()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_open = False

    @property
    def peer_closed(self) -> bool:
        return self._rx.eof

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def open(self) -> None:
        import os

        if self._is_open:
            return
        if self._path is not None:
            self._fd = os.open(self._path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        assert self._fd is not None
        self._make_raw(self._fd)
        os.set_blocking(self._fd, False)
        self._loop = asyncio.get_running_loop()
        self._rx = _ReadBuffer()
        self._loop.add_reader(self._fd, self._on_readable)
        self._is_open = True
        logger.info("Opened PTY transport %s", self.port_name)

    @staticmethod
    def _make_raw(fd: int) -> None:
        import termios
        import tty

        try:
            tty.setraw(fd)
        except termios.error:  # not a terminal, or the platform refuses: carry on with the descriptor as is
            pass

    def _on_readable(self) -> None:
        import os

        assert self._fd is not None
        try:
            chunk = os.read(self._fd, 65536)
        except BlockingIOError:
            return
        except OSError:  # EIO: every other handle on the pty has been closed
            chunk = b""
        if chunk:
            self._rx.feed(chunk)
        else:
            if self._loop is not None:
                self._loop.remove_reader(self._fd)
            self._rx.set_eof()

    async def close(self) -> None:
        import os

        if not self._is_open:
            return
        self._is_open = False
        if self._fd is not None:
            if self._loop is not None:
                self._loop.remove_reader(self._fd)
            if self._owns_fd:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
        self._rx.wake()  # let a waiting reader notice the transport is closed
        logger.info("Closed PTY transport %s", self.port_name)

    async def write(self, data: bytes) -> int:
        import errno
        import os

        if not self._is_open or self._fd is None:
            raise RuntimeError("PtyTransport is not open.")
        if self.peer_closed:
            raise ConnectionError("PTY peer has closed the connection")
        view = memoryview(data)
        while view:
            try:
                written = os.write(self._fd, view)
            except BlockingIOError:
                await self._wait_writable()
                continue
            except OSError as exc:
                if exc.errno == errno.EIO:
                    self._rx.set_eof()
                    raise ConnectionError("PTY peer has closed the connection") from exc
                raise
            view = view[written:]
        return len(data)

    async def _wait_writable(self) -> None:
        assert self._loop is not None and self._fd is not None
        ready: asyncio.Future[None] = self._loop.create_future()
        self._loop.add_writer(self._fd, lambda: None if ready.done() else ready.set_result(None))
        try:
            await ready
        finally:
            if self._fd is not None:
                self._loop.remove_writer(self._fd)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self._is_open:
            raise RuntimeError("PtyTransport is not open.")
        return await self._rx.read(size, timeout_ms, lambda: self._is_open)

    async def set_pin_state(self, pin: str, state: bool) -> None:
        """A pty has no modem control lines; known pins are accepted and ignored."""
        _pin_key(pin)


class PtySerialPair:
    """Native POSIX pseudo-terminal pair: ``host`` is the master side and ``device`` the slave side.

    Both ends are real file descriptors, so bytes written on one come out of the other through the
    kernel exactly as over a serial cable. ``slave_pts_path`` is the path of the slave device
    (for example ``/dev/pts/7``) that another program, or :class:`HardwareSerialTransport`, can open.
    """

    def __init__(self) -> None:
        import os

        if os.name == "nt":
            raise NotImplementedError("PtySerialPair is only supported on POSIX systems (Linux/macOS).")

        import pty

        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_pts_path = os.ttyname(self.slave_fd)
        self.host = PtyTransport(fd=self.master_fd, port_name="PTY_MASTER", owns_fd=False)
        self.device = PtyTransport(fd=self.slave_fd, port_name=self.slave_pts_path, owns_fd=False)
        self._closed = False

    async def open(self) -> None:
        await self.host.open()
        await self.device.open()

    async def close(self) -> None:
        import os

        await self.host.close()
        await self.device.close()
        if not self._closed:
            self._closed = True
            for fd in (self.master_fd, self.slave_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass


class WindowsNamedPipeTransport(AsyncTransport):
    """Genuine Windows named-pipe transport (``\\\\.\\pipe\\<name>``) built on the asyncio Proactor loop.

    Two roles connect through the operating system's pipe, in this or another process (for example
    a terminal emulator, a hypervisor virtual COM port or another OmniUART instance):

    - ``role="server"`` creates the pipe on :meth:`open` and serves the first client that connects;
      :meth:`wait_connected` waits for it.
    - ``role="client"`` connects to an existing pipe on :meth:`open`, retrying while the server is
      still starting or busy, for up to ``connect_timeout_s``.

    I/O is overlapped, so nothing blocks the event loop. ``read`` waits up to ``timeout_ms`` for
    ``size`` bytes and returns what arrived (``None`` waits forever, ``0`` polls). When the peer
    disconnects, buffered bytes are still delivered, later reads return ``b""`` at once,
    ``peer_closed`` is true and writes raise :class:`ConnectionError`. Operations on a closed
    transport raise :class:`RuntimeError`. Only available on Windows.
    """

    PIPE_PREFIX = "\\\\.\\pipe\\"

    def __init__(self, pipe_name: str = "omniuart_vcom", role: str = "server", connect_timeout_s: float = 5.0) -> None:
        import os

        if os.name != "nt":
            raise NotImplementedError("WindowsNamedPipeTransport is only supported on Windows.")
        if role not in ("server", "client"):
            raise ValueError("role must be 'server' or 'client'")
        self.role = role
        self.pipe_name = pipe_name if pipe_name.startswith(self.PIPE_PREFIX) else f"{self.PIPE_PREFIX}{pipe_name}"
        self.connect_timeout_s = connect_timeout_s
        self._rx = _ReadBuffer()
        self._pipe: Optional[asyncio.BaseTransport] = None
        self._servers: List[Any] = []
        self._connected = asyncio.Event()
        self._resume = asyncio.Event()
        self._resume.set()
        self._is_open = False

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def peer_closed(self) -> bool:
        return self._rx.eof

    @property
    def connected(self) -> bool:
        """True while a peer is attached to the pipe."""
        return self._pipe is not None and not self._rx.eof

    def _protocol(self) -> asyncio.Protocol:
        owner = self

        class _Protocol(asyncio.Protocol):
            def connection_made(self, transport: asyncio.BaseTransport) -> None:
                if owner._pipe is not None:  # a pipe serves one peer; refuse extra clients
                    transport.close()
                    return
                owner._pipe = transport
                owner._connected.set()

            def data_received(self, data: bytes) -> None:
                owner._rx.feed(data)

            def connection_lost(self, exc: Optional[Exception]) -> None:
                owner._rx.set_eof()
                owner._resume.set()

            def pause_writing(self) -> None:
                owner._resume.clear()

            def resume_writing(self) -> None:
                owner._resume.set()

        return _Protocol()

    async def open(self) -> None:
        if self._is_open:
            return
        loop = asyncio.get_running_loop()
        if not hasattr(loop, "start_serving_pipe"):
            raise RuntimeError("Named pipes need the asyncio Proactor event loop (the Windows default).")
        self._rx = _ReadBuffer()
        self._connected = asyncio.Event()
        self._resume = asyncio.Event()
        self._resume.set()
        self._pipe = None
        if self.role == "server":
            self._servers = await loop.start_serving_pipe(self._protocol, self.pipe_name)
        else:
            deadline = time.monotonic() + self.connect_timeout_s
            while True:
                try:
                    await loop.create_pipe_connection(self._protocol, self.pipe_name)  # type: ignore[attr-defined]  # Windows ProactorEventLoop only
                    break
                except (FileNotFoundError, OSError) as exc:
                    # ERROR_FILE_NOT_FOUND: server not created yet; ERROR_PIPE_BUSY (231): all instances in use
                    if time.monotonic() >= deadline or (isinstance(exc, OSError) and getattr(exc, "winerror", None) not in (2, 231, None)):
                        raise ConnectionError(f"cannot connect to {self.pipe_name}: {exc}") from exc
                    await asyncio.sleep(0.05)
        self._is_open = True
        logger.info("Opened Windows named pipe %s as %s", self.pipe_name, self.role)

    async def wait_connected(self, timeout_s: Optional[float] = 5.0) -> bool:
        """Wait until a peer is attached. Returns False on timeout."""
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout_s)
            return True
        except asyncio.TimeoutError:
            return False

    async def close(self) -> None:
        if not self._is_open:
            return
        self._is_open = False
        if self._pipe is not None:
            self._pipe.close()
        for server in self._servers:
            server.close()
        self._servers = []
        self._rx.wake()
        self._resume.set()
        await asyncio.sleep(0)  # let the loop run connection_lost
        logger.info("Closed Windows named pipe %s", self.pipe_name)

    async def write(self, data: bytes) -> int:
        if not self._is_open:
            raise RuntimeError("WindowsNamedPipeTransport is not open.")
        if self._pipe is None or self._rx.eof:
            raise ConnectionError("no peer is connected to the named pipe")
        self._pipe.write(data)  # type: ignore[attr-defined]
        await self._resume.wait()  # back-pressure: wait while the pipe's write buffer is full
        return len(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self._is_open:
            raise RuntimeError("WindowsNamedPipeTransport is not open.")
        return await self._rx.read(size, timeout_ms, lambda: self._is_open)

    async def set_pin_state(self, pin: str, state: bool) -> None:
        """A named pipe has no modem control lines; known pins are accepted and ignored."""
        _pin_key(pin)


class WindowsNamedPipePair:
    """A named-pipe server (``host``) and client (``device``) in one process, for tests and simulation."""

    def __init__(self, name: Optional[str] = None) -> None:
        import uuid

        pipe = name or f"omniuart_{uuid.uuid4().hex[:12]}"
        self.host = WindowsNamedPipeTransport(pipe, role="server")
        self.device = WindowsNamedPipeTransport(pipe, role="client")

    async def open(self) -> None:
        await self.host.open()
        await self.device.open()
        if not await self.host.wait_connected():
            raise ConnectionError("named pipe client did not connect")

    async def close(self) -> None:
        await self.device.close()
        await self.host.close()


async def auto_detect_baudrate(
    transport_creator: Callable[[int], AsyncTransport],
    spec: ProtocolSpec,
    candidate_baudrates: Optional[List[int]] = None,
    timeout_ms: int = 500,
) -> Optional[int]:
    """Auto-detect UART baud rate by probing candidate rates with the protocol's first command."""
    candidates = candidate_baudrates or [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
    if not spec.commands:
        return None

    cmd = spec.commands[0]
    for baud in candidates:
        transport = transport_creator(baud)
        try:
            await transport.open()
            from omniuart.core.session import DeviceSession
            session = DeviceSession(spec, transport)
            exchange = await session.send(cmd.name, timeout_ms=timeout_ms)
            if exchange.response_bytes or exchange.status.value in ("ok", "success"):
                return baud
        except Exception:
            pass
        finally:
            await transport.close()
    return None
