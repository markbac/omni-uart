"""Multipart messages: data items larger than one frame, carried as packets of the same command (#347).

A :class:`~omniuart.core.models.MultipartSpec` describes the packet bodies declaratively: the first
and the following packets of a write (host to device) and of a read (device to host), the data limit
per packet, and the whole-message and per-packet CRCs. This module turns that description into:

- :func:`build_packets` and :class:`MultipartReassembler`: pure split and reassembly, with every
  check (order, packet count, message id, total length, per-packet, running and whole-message CRC);
- :class:`MultipartTransfer`: the host side over a :class:`~omniuart.core.session.SerialSession`,
  driven by the generic :class:`~omniuart.core.transfer.TransferManager` so progress, cancel and
  history behave exactly like file transfers;
- :class:`MultipartDevice`: the device side used by the simulated device.
"""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from omniuart.core.codec import CodecError, _as_bytes, decode_fields_with_layout, default_value, encode_fields, field_size
from omniuart.core.crc import calculate_crc
from omniuart.core.models import (
    CommandSpec,
    FieldSpec,
    IntegritySpec,
    MultipartPacketLayouts,
    MultipartSpec,
    ProtocolSpec,
)
from omniuart.core.transfer import TransferChunk, TransferManager, TransferMetadata, TransferProgress, TransferState

if TYPE_CHECKING:
    from omniuart.core.codec import FrameCodec
    from omniuart.core.session import Exchange, SerialSession

_MESSAGE_IDS = itertools.count(1)


class MultipartError(CodecError):
    """A multipart message is malformed: a gap, a mismatch or a bad CRC. The message says which."""


def crc_of(params: IntegritySpec, data: bytes) -> int:
    """CRC of ``data`` with the given parameters (named algorithm or custom model)."""
    try:
        return calculate_crc(data, params.algorithm, custom_model=params.to_crc_model(), transform=params.transform, carry_wrap=params.carry_wrap)
    except ValueError as exc:
        raise MultipartError(str(exc)) from None


def value_bytes(value: Any) -> bytes:
    """The whole value of a multipart item as bytes: ``bytes``, or hex text (spaces and ``0x`` allowed)."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    try:
        return _as_bytes(str(value))
    except ValueError:
        raise CodecError(f"multipart value must be bytes or hex text, got {str(value)[:40]!r}") from None


def _field_bits(spec: FieldSpec) -> Optional[int]:
    size = field_size(spec)
    return size * 8 if size else None


def _mask(spec: FieldSpec, value: int) -> int:
    bits = _field_bits(spec)
    return value & ((1 << bits) - 1) if bits else value


def _role_values(mp: MultipartSpec, data: bytes, offset: int, chunk: bytes, index: int, count: int, message_id: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "packet_number": mp.first_packet_number + index,
        "packet_count": count,
        "message_id": message_id,
        "total_length": len(data),
        "data_length": len(chunk),
        "data": chunk,
    }
    if mp.message_crc is not None:
        out["message_crc"] = crc_of(mp.message_crc, data)
        out["running_crc"] = crc_of(mp.message_crc, data[: offset + len(chunk)])
    if mp.packet_crc is not None:
        out["packet_crc"] = crc_of(mp.packet_crc, chunk)
    return out


def encode_layout(mp: MultipartSpec, layout: Sequence[FieldSpec], roles: Mapping[str, Any]) -> bytes:
    """Encode one packet body: role fields from ``roles``, every other field from its fixed or default value."""
    values: Dict[str, Any] = {}
    for spec in layout:
        role = mp.role_of(spec.name)
        if role is not None and role in roles:
            value = roles[role]
            values[spec.name] = _mask(spec, value) if isinstance(value, int) and not isinstance(value, bool) else value
        elif spec.fixed is None and spec.expression is None:
            values[spec.name] = default_value(spec)
    return encode_fields(layout, values)


def split(mp: MultipartSpec, data: bytes) -> List[Tuple[int, bytes]]:
    """``(offset, section)`` for every packet; an empty value is one packet with an empty section."""
    size = mp.max_data_per_packet
    return [(off, data[off : off + size]) for off in range(0, len(data), size)] or [(0, b"")]


def build_packets(mp: MultipartSpec, layouts: MultipartPacketLayouts, data: bytes, message_id: int) -> List[bytes]:
    """Every packet body of ``data``, built with the first and following layouts."""
    sections = split(mp, data)
    return [
        encode_layout(mp, layouts.layout(i), _role_values(mp, data, off, chunk, i, len(sections), message_id))
        for i, (off, chunk) in enumerate(sections)
    ]


def decode_packet(mp: MultipartSpec, layout: Sequence[FieldSpec], body: bytes) -> Dict[str, Any]:
    """Decode one packet body into ``{role: value}`` (the data section as bytes)."""
    fields, _ = decode_fields_with_layout(layout, body)
    out: Dict[str, Any] = {}
    for spec in layout:
        role = mp.role_of(spec.name)
        if role is None or spec.name not in fields:
            continue
        value = fields[spec.name]
        out[role] = bytes.fromhex(value) if role == "data" else value
    return out


def packet_layout_slices(mp: MultipartSpec, layouts: MultipartPacketLayouts, body: bytes) -> Tuple[str, List[Tuple[FieldSpec, int, int, Any]]]:
    """Which layout ``body`` uses ("first" or "next") and ``(field, start, end, value)`` for each field.

    Used by the dissector. The first layout is chosen when it decodes and its packet number (if any)
    is the first packet number; otherwise the following layout.
    """
    candidates: List[Tuple[str, Sequence[FieldSpec]]] = [("first", layouts.first)]
    if layouts.next is not None:
        candidates.append(("next", layouts.next))
    fallback: Optional[Tuple[str, List[Tuple[FieldSpec, int, int, Any]]]] = None
    number_field = mp.field_for("packet_number")
    for label, layout in candidates:
        try:
            fields, layout_slices = decode_fields_with_layout(layout, body)
        except CodecError:
            continue
        slices = [(spec, start, end, fields.get(spec.name)) for spec, start, end in layout_slices]
        is_first = number_field not in fields or fields[number_field] == mp.first_packet_number
        if (label == "first") == is_first or len(candidates) == 1:
            return label, slices
        fallback = fallback or (label, slices)
    if fallback is None:
        raise MultipartError("packet body matches neither the first nor the following packet layout")
    return fallback


@dataclass
class ReceivedPacket:
    """One packet accepted by the reassembler."""

    index: int
    offset: int
    data: bytes
    header: Dict[str, Any]


class MultipartReassembler:
    """Accept packets in order and check every declared header field and CRC.

    Raises :class:`MultipartError` with a clear message on a gap, an out-of-order or repeated packet,
    a message id, packet count or length mismatch, or a bad per-packet, running or whole-message CRC.
    """

    def __init__(self, mp: MultipartSpec, layouts: MultipartPacketLayouts) -> None:
        self.mp = mp
        self.layouts = layouts
        self.packets: List[ReceivedPacket] = []
        self.buffer = bytearray()
        self.message_id: Optional[int] = None
        self.packet_count: Optional[int] = None
        self.total_length: Optional[int] = None
        self.message_crc: Optional[int] = None
        self._last_short = False

    @property
    def index(self) -> int:
        """The index of the next expected packet."""
        return len(self.packets)

    def add(self, body: bytes) -> ReceivedPacket:
        mp = self.mp
        index = self.index
        if self.complete:
            raise MultipartError(f"unexpected packet after the last one (message already has {index} packet(s))")
        try:
            header = decode_packet(mp, self.layouts.layout(index), body)
        except CodecError as exc:
            raise MultipartError(f"packet {index}: cannot decode the packet body: {exc}") from None
        data: bytes = header.get("data", b"")

        expected_number = mp.first_packet_number + index
        number = header.get("packet_number")
        if number is not None and number != _mask(self._field("packet_number", index), expected_number):
            if isinstance(number, int) and number > expected_number:
                raise MultipartError(f"packet {expected_number} is missing: received packet {number} instead")
            raise MultipartError(f"packet out of order: expected packet {expected_number}, received packet {number}")
        self._same("message_id", header, index)
        self._same("packet_count", header, index)
        self._same("total_length", header, index)
        if "message_crc" in header:
            self._same("message_crc", header, index)
        if index == 0:
            self.message_id = header.get("message_id")
            self.packet_count = header.get("packet_count")
            self.total_length = header.get("total_length")
            self.message_crc = header.get("message_crc")

        if "data_length" in header and header["data_length"] != len(data):
            raise MultipartError(f"packet {index}: data length field says {header['data_length']} byte(s), the section has {len(data)}")
        if len(data) > mp.max_data_per_packet:
            raise MultipartError(f"packet {index}: {len(data)} data byte(s), over the {mp.max_data_per_packet}-byte packet limit")
        if "packet_crc" in header:
            assert mp.packet_crc is not None
            calc = crc_of(mp.packet_crc, data)
            if calc != header["packet_crc"]:
                raise MultipartError(f"packet {index}: packet CRC mismatch (received {header['packet_crc']:#x}, calculated {calc:#x})")
        offset = len(self.buffer)
        self.buffer.extend(data)
        if self.total_length is not None and len(self.buffer) > self.total_length:
            raise MultipartError(f"packet {index}: received {len(self.buffer)} byte(s), more than the total length {self.total_length}")
        if "running_crc" in header:
            assert mp.message_crc is not None
            calc = crc_of(mp.message_crc, bytes(self.buffer))
            if calc != header["running_crc"]:
                raise MultipartError(f"packet {index}: running CRC mismatch (received {header['running_crc']:#x}, calculated {calc:#x})")
        self._last_short = len(data) < mp.max_data_per_packet
        packet = ReceivedPacket(index, offset, data, header)
        self.packets.append(packet)
        if self.packet_count is not None and self.index > self.packet_count:
            raise MultipartError(f"received {self.index} packets, more than the packet count {self.packet_count}")
        return packet

    def _field(self, role: str, index: int) -> FieldSpec:
        name = self.mp.field_for(role)
        return next(f for f in self.layouts.layout(index) if f.name == name)

    def _same(self, role: str, header: Mapping[str, Any], index: int) -> None:
        if index == 0 or role not in header:
            return
        first = {"message_id": self.message_id, "packet_count": self.packet_count, "total_length": self.total_length, "message_crc": self.message_crc}[role]
        if first is not None and header[role] != first:
            raise MultipartError(f"packet {index}: {role.replace('_', ' ')} {header[role]} differs from the first packet's {first}")

    @property
    def complete(self) -> bool:
        if not self.packets:
            return False
        if self.packet_count is not None:
            return self.index >= self.packet_count
        if self.total_length is not None:
            return len(self.buffer) >= self.total_length
        return self._last_short

    def finish(self) -> bytes:
        """The reassembled data after a final check of length, packet count and whole-message CRC."""
        if not self.complete:
            raise MultipartError(f"message incomplete: {self.index} packet(s), {len(self.buffer)} byte(s) received")
        data = bytes(self.buffer)
        if self.total_length is not None and len(data) != self.total_length:
            raise MultipartError(f"total length mismatch: header says {self.total_length} byte(s), received {len(data)}")
        if self.packet_count is not None and self.index != self.packet_count:
            raise MultipartError(f"packet count mismatch: header says {self.packet_count}, received {self.index}")
        if self.message_crc is not None:
            assert self.mp.message_crc is not None
            calc = crc_of(self.mp.message_crc, data)
            if calc != self.message_crc:
                raise MultipartError(f"message CRC mismatch (received {self.message_crc:#x}, calculated {calc:#x})")
        return data


# --------------------------------------------------------------------------------------------- host side


def multipart_request(spec: ProtocolSpec, cmd: CommandSpec, params: Optional[Mapping[str, Any]]) -> Optional[Tuple[MultipartSpec, str]]:
    """The multipart definition and direction to use for this request, or ``None`` for a plain send.

    A write is multipart when the whole value is given under ``value_param`` (and not a raw packet);
    a read is multipart unless its request packet is given explicitly.
    """
    found = spec.multipart_for(cmd)
    if found is None:
        return None
    mp, direction = found
    given = params or {}
    if direction == "write":
        assert mp.write is not None
        return found if mp.value_param in given and mp.write.packet_param not in given else None
    assert mp.read is not None
    return None if mp.read.packet_param is not None and mp.read.packet_param in given else found


def split_params(mp: MultipartSpec, direction: str, params: Optional[Mapping[str, Any]]) -> Tuple[Dict[str, Any], Optional[bytes], Optional[int]]:
    """Separate the command's own parameters from the whole value and an explicit message id."""
    given = dict(params or {})
    value = given.pop(mp.value_param, None) if direction == "write" else None
    message_field = mp.field_for("message_id")
    message_id = given.pop(message_field, None) if direction == "write" else None
    return given, (value_bytes(value) if value is not None else None), (int(message_id) if message_id is not None else None)


def first_request(spec: ProtocolSpec, cmd: CommandSpec, params: Optional[Mapping[str, Any]]) -> Tuple[bytes, int]:
    """The first request frame of a multipart send and the number of request packets (for a dry run)."""
    from omniuart.core.codec import FrameCodec

    found = multipart_request(spec, cmd, params)
    codec = FrameCodec(spec)
    if found is None:
        return codec.encode_command(cmd, params or {}), 1
    mp, direction = found
    own, value, message_id = split_params(mp, direction, params)
    if direction == "write":
        assert mp.write is not None and value is not None
        packets = build_packets(mp, mp.write, value, message_id if message_id is not None else 1)
        return codec.encode_command(cmd, {**own, mp.write.packet_param: packets[0]}), len(packets)
    assert mp.read is not None
    if mp.read.packet_param is not None:
        own[mp.read.packet_param] = build_read_request(mp, 0, None)
    return codec.encode_command(cmd, own), 0  # the number of read requests is known only from the first reply


def build_read_request(mp: MultipartSpec, index: int, message_id: Optional[int]) -> bytes:
    """The request body asking for packet ``index`` of a read."""
    assert mp.read is not None
    layout = mp.read.request_layout(index)
    if not layout:
        return b""
    roles: Dict[str, Any] = {"packet_number": mp.first_packet_number + index}
    if message_id is not None:
        roles["message_id"] = message_id
    return encode_layout(mp, layout, roles)


@dataclass
class MultipartOutcome:
    """How a multipart write or read ended."""

    direction: str
    state: TransferState
    progress: TransferProgress
    packets: int = 0
    data: bytes = b""
    error: Optional[str] = None
    status: str = "ok"  # an ExchangeStatus value describing the failure, if any
    exchanges: List["Exchange"] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.state is TransferState.COMPLETED

    @property
    def committed(self) -> bool:
        """For a write: the device acknowledged every packet. For a read: the item was received intact."""
        return self.ok


class MultipartTransfer:
    """Send or receive one multipart item over an open session, with progress, cancel and history."""

    def __init__(self, spec: ProtocolSpec, command: Union[str, CommandSpec], manager: Optional[TransferManager] = None) -> None:
        cmd = command if isinstance(command, CommandSpec) else spec.get_command(command)
        if cmd is None:
            raise CodecError(f"Unknown command '{command}'")
        found = spec.multipart_for(cmd)
        if found is None:
            raise CodecError(f"command '{cmd.name}' does not use a multipart definition")
        self.spec = spec
        self.command = cmd
        self.mp, self.direction = found
        self.manager = manager or TransferManager()
        self._cancel = asyncio.Event()

    @property
    def progress(self) -> TransferProgress:
        return self.manager.progress

    def cancel(self) -> None:
        """Stop before the next packet."""
        self._cancel.set()

    def _configure(self) -> None:
        caps = self.manager.capabilities
        caps.max_chunk_size = self.mp.max_data_per_packet
        caps.min_chunk_size = min(caps.min_chunk_size, self.mp.max_data_per_packet)

    def _fail(self, message: str, status: str, packets: int, exchanges: List["Exchange"], data: bytes = b"") -> MultipartOutcome:
        if self.manager.state not in (TransferState.FAILED, TransferState.CANCELLED):
            self.manager.abort(message)
        return MultipartOutcome(self.direction, TransferState.FAILED, self.manager.progress, packets, data, message, status, exchanges)

    def _cancelled(self, packets: int, exchanges: List["Exchange"]) -> MultipartOutcome:
        self.manager.cancel("cancelled")
        return MultipartOutcome(self.direction, TransferState.CANCELLED, self.manager.progress, packets, b"", "cancelled", "cancelled", exchanges)

    async def write(
        self,
        session: "SerialSession",
        params: Optional[Mapping[str, Any]],
        value: Optional[bytes] = None,
        message_id: Optional[int] = None,
        on_progress: Optional[Callable[[TransferProgress], None]] = None,
    ) -> MultipartOutcome:
        """Split ``value`` and send it packet by packet; each packet must be acknowledged."""
        from omniuart.core.session import ExchangeStatus

        if self.direction != "write":
            raise CodecError(f"command '{self.command.name}' is a multipart read, not a write")
        mp = self.mp
        assert mp.write is not None
        own, given_value, given_id = split_params(mp, "write", params)
        data = value if value is not None else given_value
        if data is None:
            raise CodecError(f"multipart write '{self.command.name}' needs the whole value in '{mp.value_param}'")
        if not data:
            raise CodecError(f"multipart write '{self.command.name}': the value is empty")
        msg_id = message_id if message_id is not None else given_id if given_id is not None else next(_MESSAGE_IDS)
        packets = build_packets(mp, mp.write, data, msg_id)
        # Validate every packet against the command before sending the first one.
        for body in packets:
            session.codec.encode_command(self.command, {**own, mp.write.packet_param: body})

        self._configure()
        manager = self.manager
        ok, err = manager.prepare_upload(TransferMetadata(file_name=self.command.name, total_size=len(data)), data, chunk_size=mp.max_data_per_packet)
        if not ok:
            return self._fail(err or "cannot start the write", ExchangeStatus.INVALID_RESPONSE.value, 0, [])
        assert manager._window_controller is not None
        manager._window_controller.max_retries = mp.retries
        manager.start_transfer()
        if on_progress:
            on_progress(manager.progress)
        exchanges: List["Exchange"] = []
        sent = 0
        while manager.state is TransferState.TRANSFERRING:
            chunks = manager.get_next_chunks()
            if not chunks:
                break
            for chunk in chunks:
                if self._cancel.is_set():
                    return self._cancelled(sent, exchanges)
                exchange = await session.send(self.command, {**own, mp.write.packet_param: packets[chunk.sequence_number]}, multipart=False)
                exchanges.append(exchange)
                number = mp.first_packet_number + chunk.sequence_number
                if exchange.ok:
                    sent += 1
                    manager.acknowledge_chunk(chunk.sequence_number)
                elif exchange.status in (ExchangeStatus.DEVICE_ERROR, ExchangeStatus.TRANSPORT_ERROR):
                    return self._fail(f"packet {number} of {len(packets)}: {exchange.error}", exchange.status.value, sent, exchanges)
                else:
                    can_retry, _ = manager.handle_chunk_timeout(chunk.sequence_number)
                    if not can_retry:
                        return self._fail(f"packet {number} of {len(packets)} not acknowledged: {exchange.error}", exchange.status.value, sent, exchanges)
                if on_progress:
                    on_progress(manager.progress)
        manager.verify_and_commit()
        if on_progress:
            on_progress(manager.progress)
        return MultipartOutcome("write", manager.state, manager.progress, sent, b"", manager.progress.error_message, "ok", exchanges)

    async def read(
        self,
        session: "SerialSession",
        params: Optional[Mapping[str, Any]] = None,
        on_progress: Optional[Callable[[TransferProgress], None]] = None,
    ) -> MultipartOutcome:
        """Request packets until the message is complete, checking each one, and return the data."""
        from omniuart.core.session import ExchangeStatus

        if self.direction != "read":
            raise CodecError(f"command '{self.command.name}' is a multipart write, not a read")
        mp = self.mp
        assert mp.read is not None
        own = dict(params or {})
        own.pop(mp.value_param, None)
        reasm = MultipartReassembler(mp, mp.read)
        self._configure()
        manager = self.manager
        exchanges: List["Exchange"] = []
        retries = mp.retries if mp.read.packet_param is not None else 0  # without a packet number a repeat asks for the next one
        while not reasm.complete:
            if self._cancel.is_set():
                return self._cancelled(reasm.index, exchanges)
            request = dict(own)
            if mp.read.packet_param is not None:
                request[mp.read.packet_param] = build_read_request(mp, reasm.index, reasm.message_id)
            exchange = await session.send(self.command, request, multipart=False, retries=retries, force_retry=retries > 0)
            exchanges.append(exchange)
            number = mp.first_packet_number + reasm.index
            if not exchange.ok:
                return self._fail(f"packet {number}: {exchange.error}", exchange.status.value, reasm.index, exchanges, bytes(reasm.buffer))
            raw = exchange.fields.get(mp.read.packet_field, "")
            try:
                body = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
                packet = reasm.add(body)
            except (MultipartError, ValueError) as exc:
                return self._fail(str(exc), ExchangeStatus.INVALID_RESPONSE.value, reasm.index, exchanges, bytes(reasm.buffer))
            if packet.index == 0:
                total = reasm.total_length or 0
                if total > 0:
                    ok, err = manager.prepare_download(TransferMetadata(file_name=self.command.name, total_size=total))
                    if not ok:
                        return self._fail(err or "cannot receive the item", ExchangeStatus.INVALID_RESPONSE.value, 1, exchanges)
                    manager.progress.total_chunks = reasm.packet_count or 0
            if manager.state is TransferState.TRANSFERRING and packet.data:
                accepted, err = manager.receive_chunk(TransferChunk(packet.index, packet.offset, len(packet.data), packet.data))
                if not accepted:
                    return self._fail(f"packet {number}: {err}", ExchangeStatus.INVALID_RESPONSE.value, reasm.index, exchanges)
            if on_progress:
                on_progress(manager.progress)
        try:
            data = reasm.finish()
        except MultipartError as exc:
            return self._fail(str(exc), ExchangeStatus.INVALID_RESPONSE.value, reasm.index, exchanges, bytes(reasm.buffer))
        if (reasm.total_length or 0) > 0:
            done, _, err = manager.finish_download()
            if not done:
                return self._fail(err or "reassembly failed", ExchangeStatus.INVALID_RESPONSE.value, reasm.index, exchanges, data)
        else:
            manager.state = manager.progress.state = TransferState.COMPLETED
        if on_progress:
            on_progress(manager.progress)
        return MultipartOutcome("read", TransferState.COMPLETED, manager.progress, reasm.index, data, None, "ok", exchanges)


def outcome_exchange(cmd: CommandSpec, mp: MultipartSpec, outcome: MultipartOutcome) -> "Exchange":
    """Summarise a multipart transfer as one :class:`Exchange`, so every front end can report it."""
    from omniuart.core.codec import DecodedFrame
    from omniuart.core.session import Exchange, ExchangeStatus

    exchanges = outcome.exchanges
    summary = Exchange(
        command=cmd.name,
        request=b"".join(e.request for e in exchanges),
        response_bytes=b"".join(e.response_bytes for e in exchanges),
        latency_ms=sum(e.latency_ms for e in exchanges),
    )
    for ex in exchanges:
        summary.frames.extend(ex.frames)
        summary.unsolicited.extend(ex.unsolicited)
    fields: Dict[str, Any] = {"packets": outcome.packets, "total_length": outcome.progress.total_bytes if outcome.direction == "write" else len(outcome.data)}
    if outcome.direction == "read":
        fields[mp.value_param] = outcome.data.hex()
    summary.multipart = {
        "name": mp.name,
        "direction": outcome.direction,
        "packets": outcome.packets,
        "state": outcome.state.value,
        "progress": outcome.progress.to_dict(),
        "data": outcome.data if outcome.direction == "read" else None,
    }
    if outcome.ok:
        summary.response = DecodedFrame(raw=summary.response_bytes, kind="response", name=cmd.name, fields=fields)
    else:
        summary.status = ExchangeStatus(outcome.status) if outcome.status in {s.value for s in ExchangeStatus} else ExchangeStatus.INVALID_RESPONSE
        summary.error = f"multipart {outcome.direction} '{cmd.name}' failed: {outcome.error}"
        if exchanges and exchanges[-1].response is not None:
            summary.response = exchanges[-1].response
    return summary


# ------------------------------------------------------------------------------------------- device side


def _default_item(mp: MultipartSpec) -> bytes:
    size = mp.max_data_per_packet * 2 + mp.max_data_per_packet // 2 + 1
    return bytes((i * 7 + 3) & 0xFF for i in range(size))


class MultipartDevice:
    """The device side of every multipart definition, for the simulated device.

    Writes are reassembled and stored per item; an item is identified by the command's other
    parameters (for example a fixed data item id), so a read with the same parameters returns what
    was written. A malformed write is refused with the protocol's first error reply (a NAK).
    """

    def __init__(self, spec: ProtocolSpec) -> None:
        self.spec = spec
        self.items: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], bytes] = {}
        self._writes: Dict[str, MultipartReassembler] = {}
        self._reads: Dict[str, Tuple[List[bytes], int]] = {}
        self.errors: List[str] = []

    def _key(self, mp: MultipartSpec, params: Mapping[str, Any], carrier: Optional[str]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
        skip = {carrier, mp.field_for("message_id")}
        return mp.name, tuple(sorted((k, str(v)) for k, v in params.items() if k not in skip))

    def handles(self, cmd: CommandSpec) -> bool:
        return self.spec.multipart_for(cmd) is not None

    def respond(self, cmd: CommandSpec, params: Mapping[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """``("response", values)`` for the reply fields, or ``("error", {})`` to send a NAK."""
        found = self.spec.multipart_for(cmd)
        assert found is not None
        mp, direction = found
        try:
            return ("response", self._write(cmd, mp, params) if direction == "write" else self._read(cmd, mp, params))
        except (MultipartError, CodecError, ValueError) as exc:
            self.errors.append(f"{cmd.name}: {exc}")
            self._writes.pop(cmd.name, None)
            return "error", {}

    def _write(self, cmd: CommandSpec, mp: MultipartSpec, params: Mapping[str, Any]) -> Dict[str, Any]:
        assert mp.write is not None
        raw = params.get(mp.write.packet_param, "")
        body = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
        number_field = mp.field_for("packet_number")
        reasm = self._writes.get(cmd.name)
        first = decode_packet(mp, mp.write.first, body) if self._looks_first(mp, mp.write.first, body) else None
        if reasm is None or first is not None and reasm.packets:
            reasm = self._writes[cmd.name] = MultipartReassembler(mp, mp.write)
        packet = reasm.add(body)
        reply: Dict[str, Any] = {}
        assert cmd.response is not None
        for f in cmd.response.fields:
            if f.name == number_field:
                reply[f.name] = packet.header.get("packet_number", mp.first_packet_number + packet.index)
        if reasm.complete:
            self.items[self._key(mp, params, mp.write.packet_param)] = reasm.finish()
            del self._writes[cmd.name]
        return reply

    @staticmethod
    def _looks_first(mp: MultipartSpec, layout: Sequence[FieldSpec], body: bytes) -> bool:
        try:
            header = decode_packet(mp, layout, body)
        except CodecError:
            return False
        return bool(header.get("packet_number", mp.first_packet_number) == mp.first_packet_number)

    def _read(self, cmd: CommandSpec, mp: MultipartSpec, params: Mapping[str, Any]) -> Dict[str, Any]:
        assert mp.read is not None and cmd.response is not None
        index: Optional[int] = None
        if mp.read.packet_param is not None:
            raw = params.get(mp.read.packet_param, "")
            body = bytes.fromhex(raw) if isinstance(raw, str) else bytes(raw)
            for layout in (mp.read.request_first, mp.read.request_next):
                if not body or not layout:
                    continue
                try:
                    header = decode_packet(mp, layout, body)
                except CodecError:
                    continue
                if "packet_number" in header:
                    index = int(header["packet_number"]) - mp.first_packet_number
                    break
        packets, cursor = self._reads.get(cmd.name, ([], 0))
        if index is None:
            index = cursor if packets and cursor < len(packets) else 0
        if index == 0 or not packets:
            data = self.items.get(self._key(mp, params, mp.read.packet_param), _default_item(mp))
            packets = build_packets(mp, mp.read, data, next(_MESSAGE_IDS))
        if not 0 <= index < len(packets):
            raise MultipartError(f"packet {mp.first_packet_number + index} does not exist")
        self._reads[cmd.name] = (packets, index + 1)
        return {mp.read.packet_field: packets[index]}


def device_reply(device: MultipartDevice, codec: "FrameCodec", cmd: CommandSpec, fields: Mapping[str, Any]) -> bytes:
    """The frame a simulated device sends for one multipart packet: the response, or a NAK.

    The NAK is the protocol's first declared error reply; without one the device stays silent.
    """
    kind, values = device.respond(cmd, fields)
    if kind == "response":
        return codec.encode_response(cmd, values)
    if device.spec.error_replies:
        return codec.encode_message(device.spec.error_replies[0].id, b"")
    return b""


__all__ = [
    "device_reply",
    "MultipartDevice",
    "MultipartError",
    "MultipartOutcome",
    "MultipartReassembler",
    "MultipartTransfer",
    "build_packets",
    "build_read_request",
    "decode_packet",
    "first_request",
    "multipart_request",
    "outcome_exchange",
    "packet_layout_slices",
    "split",
    "value_bytes",
]
