"""Spec-Compliant Virtual Device Simulators & Endpoint Emulators for OmniUART.

Provides automated, stateful simulation endpoints (IoT Sensors, AT Modems, Modbus RTU Slaves)
that generate spec-compliant responses, error frames, and telemetry over virtual serial interfaces.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, List, Optional, Union

from omniuart.core.crc import calculate_crc
from omniuart.core.models import CommandSpec, FramingConfig, ProtocolMeta, ProtocolSpec, SerialConfig, load_protocol
from omniuart.core.transport import AsyncTransport, VirtualTransport

logger = logging.getLogger(__name__)


class BaseDeviceSimulator:
    """Stateful virtual device emulator driven by an OmniUART ProtocolSpec."""

    def __init__(
        self,
        spec: ProtocolSpec,
        transport: Optional[AsyncTransport] = None,
        latency_ms: float = 5.0,
        fault_drop_rate: float = 0.0,
    ) -> None:
        self.spec = spec
        self.transport = transport or VirtualTransport(protocol=spec)
        self.latency_ms = latency_ms
        self.fault_drop_rate = fault_drop_rate

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._state: Dict[str, Any] = {"power": True, "rx_count": 0, "tx_count": 0}

    async def start(self) -> None:
        """Start the virtual device simulator background processing loop."""
        if self._running:
            return
        if not self.transport.is_open:
            await self.transport.open()
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info(f"Simulator started for protocol '{self.spec.metadata.name}'.")

    async def stop(self) -> None:
        """Stop the simulator loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info(f"Simulator stopped for protocol '{self.spec.metadata.name}'.")

    async def _listen_loop(self) -> None:
        """Continuously read request frames, process logic, and send responses."""
        buf = bytearray()
        while self._running:
            try:
                chunk = await self.transport.read(size=1024, timeout_ms=100)
                if not chunk:
                    await asyncio.sleep(0.01)
                    continue

                buf.extend(chunk)
                resp = self.process_incoming_bytes(buf)
                if resp:
                    if self.latency_ms > 0:
                        await asyncio.sleep(self.latency_ms / 1000.0)
                    if random.random() >= self.fault_drop_rate:
                        await self.transport.write(resp)
                        self._state["tx_count"] += 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulator loop error: {e}")
                await asyncio.sleep(0.05)

    def process_incoming_bytes(self, buf: bytearray) -> Optional[bytes]:
        """Parse frame buffer and return calculated spec-compliant response bytes."""
        if not buf:
            return None

        self._state["rx_count"] += 1
        raw_text = buf.decode("utf-8", errors="ignore")

        # Handle delimited ASCII protocols (e.g. AT commands)
        if self.spec.framing.type.value == "delimited":
            buf.clear()
            return self.handle_delimited_command(raw_text.strip())

        # Handle binary protocols
        buf.clear()
        return self.handle_binary_command(bytes(buf))

    def handle_delimited_command(self, cmd_str: str) -> bytes:
        """Handle ASCII delimited text command string."""
        if not cmd_str:
            return b""
        suffix = self.spec.framing.suffix or "\r\n"

        if cmd_str.upper() in ("AT", "PING"):
            return f"OK{suffix}".encode("utf-8")

        return f"OK{suffix}".encode("utf-8")

    def handle_binary_command(self, data: bytes) -> bytes:
        """Handle binary byte array command frame."""
        cmd_id = data[4] if len(data) > 4 else 0x01
        resp = bytearray([0xAA, 0x55, 0x02, 0x00, cmd_id, 0x00])
        crc = calculate_crc(resp[2:], "crc16_modbus")
        resp.extend(crc.to_bytes(2, "little"))
        return bytes(resp)


class ATModemSimulator(BaseDeviceSimulator):
    """Specialized virtual simulator for AT Command Cellular / GNSS Modems."""

    def __init__(
        self,
        spec: Optional[ProtocolSpec] = None,
        transport: Optional[AsyncTransport] = None,
    ) -> None:
        if spec is None:
            spec = ProtocolSpec(
                metadata=ProtocolMeta(name="Virtual AT Modem", version="1.0.0"),
                serial_config=SerialConfig(baudrate=115200),
                framing=FramingConfig(type="delimited", prefix="AT", suffix="\r\n"),
                commands=[],
            )
        super().__init__(spec=spec, transport=transport)
        self.signal_quality = 24
        self.battery_mv = 3850
        self.creg_status = 1  # 1 = Registered, home network

    def handle_delimited_command(self, cmd_str: str) -> bytes:
        cmd = cmd_str.strip().upper()
        suffix = "\r\n"

        if cmd in ("AT", "AT\r", "AT\n"):
            return f"OK{suffix}".encode("utf-8")
        elif cmd.startswith("AT+CSQ"):
            return f"+CSQ: {self.signal_quality},99{suffix}{suffix}OK{suffix}".encode("utf-8")
        elif cmd.startswith("AT+CBC"):
            return f"+CBC: 0,{self.battery_mv}{suffix}{suffix}OK{suffix}".encode("utf-8")
        elif cmd.startswith("AT+CREG?"):
            return f"+CREG: 0,{self.creg_status}{suffix}{suffix}OK{suffix}".encode("utf-8")
        elif cmd.startswith("AT+CGREG?"):
            return f"+CGREG: 0,1{suffix}{suffix}OK{suffix}".encode("utf-8")
        elif cmd.startswith("AT+GSN") or cmd.startswith("AT+CGSN"):
            return f"867530901234567{suffix}{suffix}OK{suffix}".encode("utf-8")
        elif cmd.startswith("ATD") or "ENTERDATAMODE" in cmd:
            return f"CONNECT 115200{suffix}".encode("utf-8")
        elif cmd.startswith("AT+CMGS="):
            return f"> ".encode("utf-8")

        return f"OK{suffix}".encode("utf-8")


class IoTSensorSimulator(BaseDeviceSimulator):
    """Specialized virtual simulator for IoT Binary Sensor Nodes with periodic telemetry broadcasts."""

    def __init__(
        self,
        spec: Optional[ProtocolSpec] = None,
        transport: Optional[AsyncTransport] = None,
        telemetry_interval_sec: float = 1.0,
    ) -> None:
        if spec is None:
            spec = ProtocolSpec(
                metadata=ProtocolMeta(name="Virtual IoT Sensor Node", version="1.0.0"),
                serial_config=SerialConfig(baudrate=115200),
                framing=FramingConfig(type="binary"),
                commands=[],
            )
        super().__init__(spec=spec, transport=transport)
        self.telemetry_interval_sec = telemetry_interval_sec
        self.temperature_c = 22.5
        self.humidity_pct = 45.0
        self._telemetry_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        await super().start()
        self._telemetry_task = asyncio.create_task(self._periodic_telemetry_loop())

    async def stop(self) -> None:
        if self._telemetry_task:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass
            self._telemetry_task = None
        await super().stop()

    async def _periodic_telemetry_loop(self) -> None:
        """Broadcast periodic sensor telemetry reading frames."""
        while self._running:
            await asyncio.sleep(self.telemetry_interval_sec)
            self.temperature_c += random.uniform(-0.2, 0.2)
            self.humidity_pct += random.uniform(-0.5, 0.5)

            # Build binary sensor telemetry frame: [0x55, 0xAA, temp_int, temp_frac, hum_int, CRC16]
            t_int = int(self.temperature_c)
            t_frac = int((self.temperature_c - t_int) * 100)
            h_int = int(self.humidity_pct)
            frame = bytearray([0x55, 0xAA, 0x81, t_int & 0xFF, t_frac & 0xFF, h_int & 0xFF])
            crc = calculate_crc(frame[2:], "crc16_modbus")
            frame.extend(crc.to_bytes(2, "little"))

            if self.transport and self.transport.is_open:
                await self.transport.write(bytes(frame))


class ModbusRtuSimulator(BaseDeviceSimulator):
    """Specialized virtual simulator for Modbus RTU Slave devices."""

    def __init__(
        self,
        slave_address: int = 1,
        spec: Optional[ProtocolSpec] = None,
        transport: Optional[AsyncTransport] = None,
    ) -> None:
        if spec is None:
            spec = ProtocolSpec(
                metadata=ProtocolMeta(name="Virtual Modbus RTU Slave", version="1.0.0"),
                serial_config=SerialConfig(baudrate=9600),
                framing=FramingConfig(type="binary"),
                commands=[],
            )
        super().__init__(spec=spec, transport=transport)
        self.slave_address = slave_address
        self.holding_registers: Dict[int, int] = {0: 1234, 1: 5678, 2: 9012, 3: 4321}

    def process_incoming_bytes(self, buf: bytearray) -> Optional[bytes]:
        if len(buf) < 8:
            return None

        addr = buf[0]
        func = buf[1]
        reg_addr = int.from_bytes(buf[2:4], "big")
        count = int.from_bytes(buf[4:6], "big")
        buf.clear()

        if addr != self.slave_address:
            return None

        if func == 0x03:  # Read Holding Registers
            byte_count = count * 2

            resp = bytearray([self.slave_address, 0x03, byte_count])
            for i in range(count):
                val = self.holding_registers.get(reg_addr + i, 0)
                resp.extend(val.to_bytes(2, "big"))

            crc = calculate_crc(resp, "crc16_modbus")
            resp.extend(crc.to_bytes(2, "little"))
            return bytes(resp)

        # Standard exception response (Illegal Function)
        err_resp = bytearray([self.slave_address, func | 0x80, 0x01])
        crc = calculate_crc(err_resp, "crc16_modbus")
        err_resp.extend(crc.to_bytes(2, "little"))
        return bytes(err_resp)
