"""Device session: encode a command, transmit it over a transport, and decode the response.

This is the one place that turns "send command X with these parameters" into bytes on a link and a
decoded answer, so the CLI, script runner, web API and desktop GUI all behave identically.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Union

from omniuart.core.codec import CodecError, DecodedFrame, FrameCodec
from omniuart.core.models import CommandSpec, ProtocolSpec
from omniuart.core.recorder import SessionRecorder
from omniuart.core.transport import AsyncTransport, HardwareSerialTransport, VirtualTransport


class ExchangeStatus(str, Enum):
    """Result of one request/response exchange."""

    OK = "ok"  # response received and decoded, or no response is defined for the command
    TIMEOUT = "timeout"  # a response was expected but nothing arrived in time
    INVALID_RESPONSE = "invalid_response"  # bytes arrived but are not a valid response to this command
    TRANSPORT_ERROR = "transport_error"  # the transport failed while writing or reading


@dataclass
class Exchange:
    """Everything that happened for one command."""

    command: str
    request: bytes
    status: ExchangeStatus = ExchangeStatus.OK
    response_bytes: bytes = b""
    response: Optional[DecodedFrame] = None
    latency_ms: float = 0.0
    error: Optional[str] = None
    frames: List[DecodedFrame] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status is ExchangeStatus.OK

    @property
    def fields(self) -> Dict[str, Any]:
        return dict(self.response.fields) if self.response else {}


async def read_available(transport: AsyncTransport, timeout_ms: int, gap_ms: int = 30) -> bytes:
    """Read whatever the device sends: wait ``timeout_ms`` for the first byte, then until a quiet gap."""
    data = bytearray(await transport.read(size=1, timeout_ms=timeout_ms))
    while data:
        more = await transport.read(size=1, timeout_ms=gap_ms)
        if not more:
            break
        data.extend(more)
    return bytes(data)


class DeviceSession:
    """A protocol bound to an open (or openable) transport."""

    def __init__(self, spec: ProtocolSpec, transport: AsyncTransport, recorder: Optional[SessionRecorder] = None) -> None:
        self.spec = spec
        self.transport = transport
        self.recorder = recorder
        self.codec = FrameCodec(spec)

    async def __aenter__(self) -> "DeviceSession":
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def open(self) -> None:
        if not self.transport.is_open:
            await self.transport.open()

    async def close(self) -> None:
        if self.transport.is_open:
            await self.transport.close()

    def resolve(self, command: Union[str, CommandSpec]) -> CommandSpec:
        """Find a command by name, falling back to its id."""
        if isinstance(command, CommandSpec):
            return command
        cmd = self.spec.get_command(command) or self.spec.get_command_by_id(command)
        if cmd is None:
            raise CodecError(f"Unknown command '{command}'")
        return cmd

    async def send(
        self,
        command: Union[str, CommandSpec],
        params: Optional[Mapping[str, Any]] = None,
        timeout_ms: Optional[int] = None,
    ) -> Exchange:
        """Transmit ``command`` and wait for its response.

        Invalid parameters raise :class:`CodecError` before anything is written. Failures on the
        link or in the response are reported through the returned :class:`Exchange` instead.
        """
        cmd = self.resolve(command)
        request = self.codec.encode_command(cmd, params or {})
        exchange = Exchange(command=cmd.name, request=request)
        loop = asyncio.get_running_loop()
        start = loop.time()
        if self.recorder:
            self.recorder.record("tx", request, command_name=cmd.name, command_id=cmd.id, decoded_fields=dict(params or {}))
        try:
            await self.transport.write(request)
            if cmd.response is None:
                return exchange
            wait_ms = timeout_ms if timeout_ms is not None else cmd.response.timeout_ms
            await self._await_response(cmd, exchange, wait_ms)
        except Exception as exc:  # noqa: BLE001 - any link failure is reported on the exchange
            exchange.status = ExchangeStatus.TRANSPORT_ERROR
            exchange.error = f"{type(exc).__name__}: {exc}"
        exchange.latency_ms = (loop.time() - start) * 1000.0
        if self.recorder and exchange.response_bytes:
            self.recorder.record(
                "rx",
                exchange.response_bytes,
                command_name=cmd.name,
                command_id=exchange.response.message_id if exchange.response else None,
                decoded_fields=exchange.fields,
                crc_valid=None if exchange.response is None else exchange.response.ok,
                latency_ms=exchange.latency_ms,
            )
        return exchange

    async def _await_response(self, cmd: CommandSpec, exchange: Exchange, timeout_ms: int) -> None:
        loop = asyncio.get_running_loop()
        if not self.codec.is_binary:
            data = await read_available(self.transport, timeout_ms)
            exchange.response_bytes = data
            if not data:
                exchange.status, exchange.error = ExchangeStatus.TIMEOUT, f"no response to '{cmd.name}' within {timeout_ms} ms"
                return
            text = data.decode("utf-8", errors="replace").strip()
            exchange.response = DecodedFrame(raw=data, kind="response", name=cmd.name, payload=data, fields={"text": text})
            return

        deadline = loop.time() + timeout_ms / 1000.0
        buf = b""
        while True:
            remaining_ms = int((deadline - loop.time()) * 1000)
            if remaining_ms <= 0:
                break
            chunk = await self.transport.read(size=1, timeout_ms=remaining_ms)
            if not chunk:
                break
            exchange.response_bytes += chunk
            frames, buf = self.codec.extract_frames(buf + chunk, direction="response")
            for frame in frames:
                exchange.frames.append(frame)
                if not frame.ok:
                    exchange.status, exchange.error, exchange.response = ExchangeStatus.INVALID_RESPONSE, f"invalid response: {frame.error}", frame
                    return
                if frame.kind == "response":
                    if frame.name != cmd.name:
                        exchange.status = ExchangeStatus.INVALID_RESPONSE
                        exchange.error = f"response is for '{frame.name}', not '{cmd.name}'"
                    exchange.response = frame
                    return
                # Unsolicited telemetry that arrives first is kept in ``frames``; keep waiting.
        if exchange.response_bytes:
            exchange.status = ExchangeStatus.INVALID_RESPONSE
            exchange.error = "incomplete or unrecognised response bytes: " + exchange.response_bytes.hex(" ")
        else:
            exchange.status = ExchangeStatus.TIMEOUT
            exchange.error = f"no response to '{cmd.name}' within {timeout_ms} ms"


def create_transport(spec: ProtocolSpec, port: Optional[str] = None, baudrate: Optional[int] = None, virtual: bool = False) -> AsyncTransport:
    """Build the transport for a CLI/API request: a real serial port, or the simulated device."""
    if virtual and port:
        raise ValueError("choose either a serial port or the virtual device, not both")
    if virtual:
        return VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0)
    if not port:
        raise ValueError("no transport selected: give a serial port or use the virtual device")
    return HardwareSerialTransport(port, baudrate=baudrate or spec.serial_config.baudrate, serial_config=spec.serial_config)
