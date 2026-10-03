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
    """Physical serial hardware port transport using PySerial."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Optional[serial.Serial] = None

    async def open(self) -> None:
        """Open physical serial port connection."""
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
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


class PtySerialPair:
    """Native POSIX pseudo-terminal (PTY) virtual serial pair for Linux and macOS."""

    def __init__(self) -> None:
        import os
        if os.name == "nt":
            raise NotImplementedError("PtySerialPair is only supported on POSIX systems (Linux/macOS).")

        import pty
        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_pts_path = os.ttyname(self.slave_fd)
        self.host = PipeTransport(port_name="PTY_MASTER")
        self.device = PipeTransport(port_name=self.slave_pts_path)
        self.host.connect_peer(self.device)
        self.device.connect_peer(self.host)

    async def open(self) -> None:
        await self.host.open()
        await self.device.open()

    async def close(self) -> None:
        import os
        await self.host.close()
        await self.device.close()
        try:
            os.close(self.master_fd)
            os.close(self.slave_fd)
        except Exception:
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


