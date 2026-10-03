"""Transport Abstraction Layer & Virtual MCU Simulator for OmniUART."""

from __future__ import annotations

import abc
import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Tuple

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
        """Read up to `size` bytes from the transport."""
        pass

    @property
    @abc.abstractmethod
    def is_open(self) -> bool:
        """Check if transport is currently connected and open."""
        pass

    @abc.abstractmethod
    async def set_pin_state(self, pin: str, state: bool) -> None:
        """Set DTR or RTS control pin state."""
        pass

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
    ) -> None:
        self.protocol = protocol
        self.latency_ms = latency_ms
        self.jitter_ms = jitter_ms
        self.fault_crc_flip = fault_crc_flip
        self.fault_drop_rate = fault_drop_rate

        self._tx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._rx_buffer = bytearray()
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
        pin_key = pin.lower()
        if pin_key in self.pin_states:
            self.pin_states[pin_key] = state
            logger.info(f"Virtual pin '{pin_key}' set to {state}")

    def register_response(self, command_id: int, response_payload: bytes) -> None:
        """Register custom raw response bytes for a specific command ID."""
        self._rule_responses[command_id] = response_payload

    async def write(self, data: bytes) -> int:
        """Receive outbound bytes from host, process rules, and push response to RX queue."""
        if not self._is_open:
            raise RuntimeError("VirtualTransport is not open.")

        if random.random() < self.fault_drop_rate:
            logger.warning("Fault injection: Dropped outbound frame.")
            return len(data)

        # Simulate transmission latency and jitter
        delay = max(0.001, (self.latency_ms + random.uniform(-self.jitter_ms, self.jitter_ms)) / 1000.0)
        await asyncio.sleep(delay)

        # Generate response byte frame
        resp_bytes = self._generate_response(data)
        if self.fault_crc_flip and len(resp_bytes) > 2:
            # Corrupt last byte for CRC bit-flip test
            resp_bytes = resp_bytes[:-1] + bytes([resp_bytes[-1] ^ 0xFF])

        if resp_bytes:
            await self._rx_queue.put(resp_bytes)
        return len(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        """Read up to ``size`` bytes from the RX queue; surplus bytes stay buffered for the next read."""
        if not self._is_open:
            raise RuntimeError("VirtualTransport is not open.")

        end_time = (time.monotonic() + timeout_ms / 1000.0) if timeout_ms else None
        while len(self._rx_buffer) < size:
            try:
                if end_time is None:
                    chunk = await self._rx_queue.get()
                else:
                    remaining = end_time - time.monotonic()
                    if remaining <= 0:
                        break
                    chunk = await asyncio.wait_for(self._rx_queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            self._rx_buffer.extend(chunk)

        result = bytes(self._rx_buffer[:size])
        del self._rx_buffer[:size]
        return result

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

    async def write(self, data: bytes) -> int:
        if not self.is_open or not self._serial:
            raise RuntimeError("HardwareSerialTransport is not open.")
        return await asyncio.to_thread(self._serial.write, data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self.is_open or not self._serial:
            raise RuntimeError("HardwareSerialTransport is not open.")
        self._serial.timeout = self.timeout if timeout_ms is None else timeout_ms / 1000.0
        return await asyncio.to_thread(self._serial.read, size)

    async def set_pin_state(self, pin: str, state: bool) -> None:
        if not self.is_open or not self._serial:
            raise RuntimeError("HardwareSerialTransport is not open.")
        pin_key = pin.lower()
        if pin_key == "dtr":
            self._serial.dtr = state
        elif pin_key == "rts":
            self._serial.rts = state
        else:
            raise ValueError(f"Unsupported pin: {pin}")


class PipeTransport(AsyncTransport):
    """Bidirectional in-memory pipe transport representing one endpoint of a virtual serial pair."""

    def __init__(self, port_name: str = "VIRTUAL_COM1") -> None:
        self.port_name = port_name
        self._rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._buffer = bytearray()
        self._peer: Optional[PipeTransport] = None
        self._is_open = False

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
        await self._peer._rx_queue.put(data)
        return len(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self._is_open:
            raise RuntimeError("PipeTransport is not open.")

        timeout_sec = (timeout_ms / 1000.0) if timeout_ms else None
        end_time = (time.monotonic() + timeout_sec) if timeout_sec is not None else None

        while len(self._buffer) < size:
            if end_time is not None:
                remaining = end_time - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    chunk = await asyncio.wait_for(self._rx_queue.get(), timeout=remaining)
                    self._buffer.extend(chunk)
                except asyncio.TimeoutError:
                    break
            else:
                chunk = await self._rx_queue.get()
                self._buffer.extend(chunk)

        result = bytes(self._buffer[:size])
        self._buffer = self._buffer[size:]
        return result

    async def set_pin_state(self, pin: str, state: bool) -> None:
        pass


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
        self._buffer = bytearray()
        self._data_event: Optional[asyncio.Event] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_open = False
        self.peer_closed = False

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
        self._data_event = asyncio.Event()
        self._loop.add_reader(self._fd, self._on_readable)
        self.peer_closed = False
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

        assert self._fd is not None and self._data_event is not None
        try:
            chunk = os.read(self._fd, 65536)
        except BlockingIOError:
            return
        except OSError:  # EIO: every other handle on the pty has been closed
            chunk = b""
        if chunk:
            self._buffer.extend(chunk)
        else:
            self.peer_closed = True
            if self._loop is not None:
                self._loop.remove_reader(self._fd)
        self._data_event.set()

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
        if self._data_event is not None:
            self._data_event.set()  # wake any reader so it can see the transport is closed
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
                    self.peer_closed = True
                    raise ConnectionError("PTY peer has closed the connection") from exc
                raise
            view = view[written:]
        return len(data)

    async def _wait_writable(self) -> None:
        assert self._loop is not None and self._fd is not None
        ready: asyncio.Future[None] = self._loop.create_future()
        self._loop.add_writer(self._fd, lambda: ready.done() or ready.set_result(None))
        try:
            await ready
        finally:
            if self._fd is not None:
                self._loop.remove_writer(self._fd)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self._is_open or self._data_event is None:
            raise RuntimeError("PtyTransport is not open.")

        deadline = None if timeout_ms is None else time.monotonic() + timeout_ms / 1000.0
        while len(self._buffer) < size and not self.peer_closed and self._is_open:
            self._data_event.clear()
            if deadline is None:
                await self._data_event.wait()
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                await asyncio.wait_for(self._data_event.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                break

        result = bytes(self._buffer[:size])
        del self._buffer[:size]
        return result

    async def set_pin_state(self, pin: str, state: bool) -> None:
        """A pty has no modem control lines; the request is accepted and ignored."""


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
    """Windows Named Pipe virtual serial transport (\\\\.\\pipe\\omniuart_<name>)."""

    def __init__(self, pipe_name: str = "omniuart_vcom") -> None:
        self.pipe_name = f"\\\\.\\pipe\\{pipe_name}"
        self._is_open = False
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def open(self) -> None:
        self._is_open = True
        logger.info(f"Connected Windows Virtual Named Pipe: {self.pipe_name}")

    async def close(self) -> None:
        self._is_open = False
        logger.info(f"Closed Windows Virtual Named Pipe: {self.pipe_name}")

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def write(self, data: bytes) -> int:
        if not self._is_open:
            raise RuntimeError("WindowsNamedPipeTransport is not open.")
        await self._queue.put(data)
        return len(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self._is_open:
            raise RuntimeError("WindowsNamedPipeTransport is not open.")

        timeout_sec = (timeout_ms / 1000.0) if timeout_ms else None
        try:
            buf = bytearray()
            while len(buf) < size:
                if timeout_sec is not None:
                    chunk = await asyncio.wait_for(self._queue.get(), timeout=timeout_sec)
                else:
                    chunk = await self._queue.get()
                buf.extend(chunk)
            return bytes(buf[:size])
        except asyncio.TimeoutError:
            return bytes()

    async def set_pin_state(self, pin: str, state: bool) -> None:
        pass


