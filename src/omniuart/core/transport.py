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

from omniuart.core.crc import calculate_crc
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

        await self._rx_queue.put(resp_bytes)
        return len(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        """Read bytes from RX queue."""
        if not self._is_open:
            raise RuntimeError("VirtualTransport is not open.")

        timeout_sec = (timeout_ms / 1000.0) if timeout_ms else None
        try:
            buf = bytearray()
            while len(buf) < size:
                if timeout_sec is not None:
                    chunk = await asyncio.wait_for(self._rx_queue.get(), timeout=timeout_sec)
                else:
                    chunk = await self._rx_queue.get()
                buf.extend(chunk)
            return bytes(buf[:size])
        except asyncio.TimeoutError:
            return bytes()

    def _generate_response(self, request_bytes: bytes) -> bytes:
        """Simulate MCU frame processing and generate valid/mock response frame."""
        cmd_id = request_bytes[4] if len(request_bytes) > 4 else 0x01
        if cmd_id in self._rule_responses:
            return self._rule_responses[cmd_id]

        resp = bytearray([0xAA, 0x55, 0x02, 0x00, cmd_id, 0x00])
        crc = calculate_crc(resp[2:], "crc16_modbus")
        resp.extend(crc.to_bytes(2, "little"))
        return bytes(resp)


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
        return self._serial.write(data)

    async def read(self, size: int = 1, timeout_ms: Optional[int] = 1000) -> bytes:
        if not self.is_open or not self._serial:
            raise RuntimeError("HardwareSerialTransport is not open.")
        return self._serial.read(size)

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
