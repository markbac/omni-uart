"""Device session: encode a command, transmit it over a transport, and decode the response.

This is the one place that turns "send command X with these parameters" into bytes on a link and a
decoded answer, so the CLI, script runner, web API and desktop GUI all behave identically.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

from omniuart.core.codec import CodecError, DecodedFrame, FrameCodec
from omniuart.core.models import CommandSpec, ProtocolSpec
from omniuart.core.recorder import SessionRecorder
from omniuart.core.transport import AsyncTransport, HardwareSerialTransport, VirtualTransport


# Decides whether a received frame answers a request: (command, request values, frame) -> bool.
ResponseMatcher = Callable[[CommandSpec, Mapping[str, Any], DecodedFrame], bool]


def _same_value(sent: Any, received: Any) -> bool:
    if isinstance(sent, (int, float)) and isinstance(received, (int, float)) and not isinstance(sent, bool):
        return abs(float(sent) - float(received)) <= 1e-9 * max(1.0, abs(float(sent)))
    return bool(sent == received) or str(sent) == str(received)


class CommandBlockedError(CodecError):
    """The session is read-only and the command is not marked ``read_only``; nothing was sent."""


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
    unsolicited: List[DecodedFrame] = field(default_factory=list)  # telemetry and responses that were not this command's answer

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


class SessionState(str, Enum):
    """Session operational state."""

    CLOSED = "closed"
    OPEN = "open"
    ERROR = "error"


@dataclass
class SessionStatistics:
    """Telemetry and execution metrics for a session."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    total_latency_ms: float = 0.0
    error_count: int = 0

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / max(1, self.total_requests)


class SerialSession:
    """Canonical execution layer: frame encode/decode, request/response lifecycle, state, statistics, and retries."""

    def __init__(
        self,
        spec: ProtocolSpec,
        transport: AsyncTransport,
        recorder: Optional[SessionRecorder] = None,
        read_only: bool = False,
        matcher: Optional[ResponseMatcher] = None,
        on_unsolicited: Optional[Callable[[DecodedFrame], None]] = None,
    ) -> None:
        """``matcher`` replaces the built-in correlation (command name plus the ``correlate`` fields).

        Frames that are not the awaited response (telemetry, or a response whose correlation fields
        differ) never end the wait: they are collected in ``Exchange.unsolicited`` and passed to
        ``on_unsolicited``.
        """
        self.matcher = matcher
        self.on_unsolicited = on_unsolicited
        self.spec = spec
        self.transport = transport
        self.recorder = recorder
        self.read_only = read_only
        self.codec = FrameCodec(spec)
        self.stats = SessionStatistics()
        self.state = SessionState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.transport.is_open and self.state == SessionState.OPEN

    def reset_statistics(self) -> None:
        self.stats = SessionStatistics()

    def get_statistics(self) -> SessionStatistics:
        return self.stats

    async def __aenter__(self) -> "SerialSession":
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def open(self) -> None:
        if not self.transport.is_open:
            await self.transport.open()
        self.state = SessionState.OPEN

    async def close(self) -> None:
        if self.transport.is_open:
            await self.transport.close()
        self.state = SessionState.CLOSED

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
        retries: int = 0,
        matcher: Optional[ResponseMatcher] = None,
    ) -> Exchange:
        """Transmit ``command`` and wait for its response, optionally retrying on failure.

        Invalid parameters raise :class:`CodecError`, and a non-``read_only`` command in a read-only session raises :class:`CommandBlockedError`, before anything is written. Failures on the
        link or in the response are reported through the returned :class:`Exchange` instead.
        """
        attempts = max(1, retries + 1)
        last_exchange: Optional[Exchange] = None
        for _ in range(attempts):
            exchange = await self._send_once(command, params=params, timeout_ms=timeout_ms, matcher=matcher)
            last_exchange = exchange
            if exchange.ok:
                break
        return last_exchange  # type: ignore[return-value]

    async def _send_once(
        self,
        command: Union[str, CommandSpec],
        params: Optional[Mapping[str, Any]] = None,
        timeout_ms: Optional[int] = None,
        matcher: Optional[ResponseMatcher] = None,
    ) -> Exchange:
        cmd = self.resolve(command)
        if self.read_only and not cmd.is_read_only:
            raise CommandBlockedError(
                f"read-only session: '{cmd.name}' is {cmd.safety.value}, only read_only commands may be sent"
            )
        request = self.codec.encode_command(cmd, params or {})
        exchange = Exchange(command=cmd.name, request=request)
        loop = asyncio.get_running_loop()
        start = loop.time()
        if self.recorder:
            self.recorder.record("tx", request, command_name=cmd.name, command_id=cmd.id, decoded_fields=dict(params or {}))
        try:
            await self.transport.write(request)
            if cmd.response is None:
                exchange.latency_ms = (loop.time() - start) * 1000.0
                self._update_stats(exchange, len(request), 0)
                return exchange
            wait_ms = timeout_ms if timeout_ms is not None else cmd.response.timeout_ms
            await self._await_response(cmd, exchange, wait_ms, self._request_values(cmd, params), matcher or self.matcher)
        except Exception as exc:  # noqa: BLE001 - any link failure is reported on the exchange
            exchange.status = ExchangeStatus.TRANSPORT_ERROR
            exchange.error = f"{type(exc).__name__}: {exc}"
        exchange.latency_ms = (loop.time() - start) * 1000.0
        self._update_stats(exchange, len(request), len(exchange.response_bytes))
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

    def _update_stats(self, exchange: Exchange, tx_len: int, rx_len: int) -> None:
        self.stats.total_requests += 1
        self.stats.bytes_sent += tx_len
        self.stats.bytes_received += rx_len
        self.stats.total_latency_ms += exchange.latency_ms
        if exchange.ok:
            self.stats.successful_requests += 1
        else:
            self.stats.failed_requests += 1
    @staticmethod
    def _request_values(cmd: CommandSpec, params: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        given = params or {}
        return {p.name: given.get(p.name, p.default) for p in cmd.parameters}

    def _matches(self, cmd: CommandSpec, values: Mapping[str, Any], frame: DecodedFrame, matcher: Optional[ResponseMatcher]) -> bool:
        if matcher is not None:
            return matcher(cmd, values, frame)
        return all(
            name in frame.fields and _same_value(values.get(name), frame.fields[name])
            for name in self.spec.correlation_fields(cmd)
        )

    def _unsolicited(self, exchange: Exchange, frame: DecodedFrame) -> None:
        exchange.unsolicited.append(frame)
        if self.on_unsolicited:
            self.on_unsolicited(frame)

    async def _await_response(
        self,
        cmd: CommandSpec,
        exchange: Exchange,
        timeout_ms: int,
        values: Mapping[str, Any],
        matcher: Optional[ResponseMatcher] = None,
    ) -> None:
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
                    if frame.name != cmd.name and matcher is None:
                        exchange.status = ExchangeStatus.INVALID_RESPONSE
                        exchange.error = f"response is for '{frame.name}', not '{cmd.name}'"
                        exchange.response = frame
                        return
                    if self._matches(cmd, values, frame, matcher):
                        exchange.response = frame
                        return
                # Telemetry, or a response whose correlation fields differ: not ours, keep waiting.
                self._unsolicited(exchange, frame)
        if exchange.unsolicited and not buf:
            exchange.status = ExchangeStatus.TIMEOUT
            exchange.error = f"no matching response to '{cmd.name}' within {timeout_ms} ms ({len(exchange.unsolicited)} other frame(s) ignored)"
        elif exchange.response_bytes:
            exchange.status = ExchangeStatus.INVALID_RESPONSE
            exchange.error = "incomplete or unrecognised response bytes: " + exchange.response_bytes.hex(" ")
        else:
            exchange.status = ExchangeStatus.TIMEOUT
            exchange.error = f"no response to '{cmd.name}' within {timeout_ms} ms"


class DeviceSession(SerialSession):
    """A protocol bound to an open (or openable) transport (alias / subclass of SerialSession)."""



def create_transport(spec: ProtocolSpec, port: Optional[str] = None, baudrate: Optional[int] = None, virtual: bool = False) -> AsyncTransport:
    """Build the transport for a CLI/API request: a real serial port, or the simulated device."""
    if virtual and port:
        raise ValueError("choose either a serial port or the virtual device, not both")
    if virtual:
        return VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0)
    if not port:
        raise ValueError("no transport selected: give a serial port or use the virtual device")
    return HardwareSerialTransport(port, baudrate=baudrate or spec.serial_config.baudrate, serial_config=spec.serial_config)
