"""Spec-Compliant Virtual Device Simulators & Endpoint Emulators for OmniUART.

Provides automated, stateful simulation endpoints (IoT Sensors, AT Modems, Modbus RTU Slaves)
that generate spec-compliant responses, error frames, and telemetry over virtual serial interfaces.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Dict, Optional

from omniuart.core.codec import CodecError, DecodedFrame, FrameCodec, validate_fields
from omniuart.core.crc import calculate_crc
from omniuart.core.models import CommandSpec, FramingConfig, FramingType, ProtocolMeta, ProtocolSpec, SerialConfig
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
        frame_timeout_ms: float = 50.0,
    ) -> None:
        self.spec = spec
        self.frame_timeout_ms = frame_timeout_ms
        self.transport = transport or VirtualTransport(protocol=spec)
        self.latency_ms = latency_ms
        self.fault_drop_rate = fault_drop_rate

        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._state: Dict[str, Any] = {"power": True, "rx_count": 0, "rx_errors": 0, "tx_count": 0}
        self.codec = FrameCodec(spec)

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
        last_rx = time.monotonic()
        while self._running:
            try:
                chunk = await self.transport.read(size=1, timeout_ms=50)
                if not chunk:
                    # Like a real UART receiver, abandon a partial frame after an idle gap so that
                    # one truncated frame cannot swallow the start of the next request.
                    if buf and (time.monotonic() - last_rx) * 1000.0 >= self.frame_timeout_ms:
                        logger.debug("Discarding %d byte(s) of incomplete frame after idle timeout", len(buf))
                        buf.clear()
                        self._state["rx_errors"] += 1
                    await asyncio.sleep(0.005)
                    continue

                last_rx = time.monotonic()
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
        """Consume complete request frames from ``buf`` and return the concatenated responses.

        Bytes that belong to an incomplete frame stay in ``buf`` until more arrive. Binary
        requests are located, validated and identified by the protocol's :class:`FrameCodec`.
        """
        if not buf:
            return None

        framing_type = getattr(self.spec.framing.type, "value", self.spec.framing.type)

        # Handle delimited ASCII protocols (e.g. AT commands): one command per line, and the
        # empty line left by a CR LF terminator pair is not a command.
        if str(framing_type).lower() == "delimited":
            raw_text = buf.decode("utf-8", errors="ignore")
            responses = bytearray()
            while True:
                end = next((i for i, ch in enumerate(raw_text) if ch in "\r\n"), -1)
                if end < 0:
                    break
                line, raw_text = raw_text[:end].strip(), raw_text[end + 1 :]
                if line:
                    self._state["rx_count"] += 1
                    responses.extend(self.handle_delimited_command(line))
            if len(raw_text) > 128:  # no terminator in sight: treat the overlong input as one command
                self._state["rx_count"] += 1
                responses.extend(self.handle_delimited_command(raw_text.strip()))
                raw_text = ""
            buf[:] = raw_text.encode("utf-8")
            return bytes(responses) or None

        frames, rest = self.codec.extract_frames(bytes(buf), direction="request")
        buf[:] = rest[-self.MAX_PENDING_BYTES :]
        responses = bytearray()
        for frame in frames:
            self._state["rx_count"] += 1
            if not frame.ok:
                # A device ignores frames it cannot validate; it does not answer them.
                self._state["rx_errors"] += 1
                logger.debug("Ignoring invalid request frame: %s", frame.error)
                continue
            responses.extend(self.handle_frame(frame))
        return bytes(responses) or None

    MAX_PENDING_BYTES = 4096

    def handle_frame(self, frame: DecodedFrame) -> bytes:
        """Answer one valid request frame; returns ``b""`` when the command has no response."""
        cmd = self.spec.get_command(frame.name or "")
        if cmd is None:
            return b""
        violation = validate_fields(cmd.parameters, frame.fields)
        if violation:
            # A compliant device refuses out-of-range parameters rather than acting on them.
            self._state["rx_errors"] += 1
            logger.debug("Ignoring '%s': %s", cmd.name, violation)
            return b""
        if cmd.response is None:
            return b""
        values = self.handle_command(cmd, frame.fields)
        if values is None:
            return b""
        try:
            return self.codec.encode_response(cmd, values)
        except CodecError as exc:
            logger.error("Cannot encode response for '%s': %s", cmd.name, exc)
            return b""

    def handle_command(self, cmd: CommandSpec, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Behaviour hook: return response field values for ``cmd``, or ``None`` to stay silent.

        The default answers every command that declares a response using the declared field
        defaults. Subclasses override this to model device state.
        """
        return {}

    def handle_delimited_command(self, cmd_str: str) -> bytes:
        """Handle ASCII delimited text command string."""
        if not cmd_str:
            return b""
        suffix = self.spec.framing.suffix or "\r\n"

        if cmd_str.upper() in ("AT", "PING"):
            return f"OK{suffix}".encode("utf-8")

        return f"OK{suffix}".encode("utf-8")


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
                framing=FramingConfig(type=FramingType.DELIMITED, prefix="AT", suffix="\r\n"),
                commands=[],
            )
        super().__init__(spec=spec, transport=transport)
        self.signal_quality = 24
        self.battery_mv = 3850
        self.creg_status = 1  # 1 = Registered, home network

    @staticmethod
    def _final(result: str) -> bytes:
        """V.250 framing: ``<CR><LF>result<CR><LF>``."""
        return f"\r\n{result}\r\n".encode("utf-8")

    def _info(self, line: str) -> bytes:
        return f"\r\n{line}\r\n".encode("utf-8") + self._final("OK")

    def handle_delimited_command(self, cmd_str: str) -> bytes:
        cmd = cmd_str.strip().upper()
        if not cmd:
            return b""  # an empty line is not a command
        if cmd == "AT":
            return self._final("OK")
        if cmd.startswith("AT+CSQ"):
            return self._info(f"+CSQ: {self.signal_quality},99")
        if cmd.startswith("AT+CBC"):
            return self._info(f"+CBC: 0,{self.battery_mv}")
        if cmd.startswith("AT+CREG?"):
            return self._info(f"+CREG: 0,{self.creg_status}")
        if cmd.startswith("AT+CGREG?"):
            return self._info("+CGREG: 0,1")
        if cmd.startswith("AT+GSN") or cmd.startswith("AT+CGSN"):
            return self._info("867530901234567")
        if cmd.startswith("ATD") or "ENTERDATAMODE" in cmd:
            return self._final("CONNECT 115200")
        if cmd.startswith("AT+CMGS="):
            return b"\r\n> "
        return self._final("ERROR")  # unknown command, so typos do not pass silently


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
                framing=FramingConfig(type=FramingType.BINARY),
                commands=[],
            )
        super().__init__(spec=spec, transport=transport)
        self.telemetry_interval_sec = telemetry_interval_sec
        self.temperature_c = 22.5
        self.humidity_pct = 45.0
        self._telemetry_task: Optional[asyncio.Task[None]] = None

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
            crc = calculate_crc(bytes(frame[2:]), "crc16_modbus")
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
                framing=FramingConfig(type=FramingType.BINARY),
                commands=[],
            )
        super().__init__(spec=spec, transport=transport)
        self.slave_address = slave_address
        self.holding_registers: Dict[int, int] = {0: 1234, 1: 5678, 2: 9012, 3: 4321}

    MAX_READ_REGISTERS = 125  # Modbus limit for function 0x03

    def _with_crc(self, body: bytes) -> bytes:
        return body + calculate_crc(body, "crc16_modbus").to_bytes(2, "little")

    def _exception(self, func: int, code: int) -> bytes:
        return self._with_crc(bytes([self.slave_address, func | 0x80, code]))

    def process_incoming_bytes(self, buf: bytearray) -> Optional[bytes]:
        if len(buf) < 8:
            return None

        frame = bytes(buf[:8])
        buf.clear()  # a request is exactly 8 bytes for the one function we implement
        if calculate_crc(frame[:6], "crc16_modbus") != int.from_bytes(frame[6:8], "little"):
            self._state["rx_errors"] += 1
            return None  # a bad checksum is silently dropped, as on a real bus

        addr, func = frame[0], frame[1]
        if addr != self.slave_address:
            return None  # not for us (broadcast address 0 gets no reply either)

        if func != 0x03:
            return self._exception(func, 0x01)  # Illegal Function

        reg_addr = int.from_bytes(frame[2:4], "big")
        count = int.from_bytes(frame[4:6], "big")
        if not 1 <= count <= self.MAX_READ_REGISTERS:
            return self._exception(func, 0x03)  # Illegal Data Value
        if reg_addr + count > 0x10000:
            return self._exception(func, 0x02)  # Illegal Data Address

        body = bytearray([self.slave_address, 0x03, count * 2])
        for i in range(count):
            body.extend(self.holding_registers.get(reg_addr + i, 0).to_bytes(2, "big"))
        return self._with_crc(bytes(body))
