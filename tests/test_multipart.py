"""Multipart messages: data items larger than one frame (#347).

Uses the neutral example protocol ``examples/protocols/large_item_device.yaml``: a certificate item
written in packets (header, message id, total length and whole-message CRC in the first packet) and
read in packets (packet count, total length and a per-packet CRC in the first reply, a running CRC
in the following ones), 32 data bytes per packet.
"""

from __future__ import annotations

import asyncio
import base64
import copy
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

from omniuart.core.codec import FrameCodec
from omniuart.core.dissector import dissect_frame
from omniuart.core.models import ProtocolSpec, load_protocol
from omniuart.core.multipart import (
    MultipartError,
    MultipartReassembler,
    MultipartTransfer,
    build_packets,
    decode_packet,
    encode_layout,
    first_request,
)
from omniuart.core.session import ExchangeStatus, SerialSession
from omniuart.core.simulator import BaseDeviceSimulator
from omniuart.core.transfer import TransferState
from omniuart.core.transport import VirtualTransport

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "protocols" / "large_item_device.yaml"
DATA = bytes((i * 13 + 5) & 0xFF for i in range(150))  # 5 packets of at most 32 bytes


@pytest.fixture(scope="module")
def spec() -> ProtocolSpec:
    return load_protocol(EXAMPLE)


def _raw(spec: ProtocolSpec) -> Dict[str, Any]:
    return yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))


def _transport(spec: ProtocolSpec) -> VirtualTransport:
    return VirtualTransport(spec, latency_ms=0.0, jitter_ms=0.0)


# ------------------------------------------------------------------------------------------------ schema


def test_example_protocol_declares_the_multipart_item(spec: ProtocolSpec) -> None:
    mp = spec.multipart[0]
    assert spec.multipart_for("write_certificate") == (mp, "write")
    assert spec.multipart_for("read_certificate") == (mp, "read")
    assert spec.multipart_for("ping") is None
    assert mp.role_of("reserved") is None and mp.role_of("message_crc") == "message_crc"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d["multipart"][0]["write"].update(commands=["nope"]), "is not defined"),
        (lambda d: d["multipart"][0]["write"].update(packet_param="missing"), "has no 'missing' parameter"),
        (lambda d: d["multipart"][0]["read"].update(packet_field="missing"), "has no 'missing' response field"),
        (lambda d: d["multipart"][0].pop("packet_crc"), "no 'packet_crc' CRC parameters"),
        (lambda d: d["multipart"][0].update(roles={"bogus": "x"}), "unknown multipart role"),
        (lambda d: d["multipart"][0]["read"]["first"].pop(3), "must carry the total length"),
        (lambda d: d["multipart"][0]["write"]["first"].pop(), r"has no 'data' \(data\) field"),
        (lambda d: d["commands"][1]["parameters"][1].update(type="string"), "must be of type bytes"),
        (lambda d: d["multipart"][0].update(max_data_per_packet=0), "greater than 0"),
        (lambda d: (d["multipart"][0].pop("write"), d["multipart"][0].pop("read")), "neither write nor read"),
    ],
)
def test_invalid_multipart_definitions_are_rejected_at_load_time(spec: ProtocolSpec, mutate: Any, message: str) -> None:
    data = copy.deepcopy(_raw(spec))
    mutate(data)
    with pytest.raises(ValueError, match=message):
        ProtocolSpec.model_validate(data)


def test_a_command_may_belong_to_only_one_multipart_definition(spec: ProtocolSpec) -> None:
    data = copy.deepcopy(_raw(spec))
    twin = copy.deepcopy(data["multipart"][0])
    twin["name"] = "twin"
    data["multipart"].append(twin)
    with pytest.raises(ValueError, match="is used by multipart"):
        ProtocolSpec.model_validate(data)


def test_committed_protocol_schema_includes_multipart() -> None:
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "protocol.schema.json").read_text(encoding="utf-8"))
    assert "multipart" in schema["properties"]
    assert "MultipartSpec" in schema["$defs"]


# --------------------------------------------------------------------------------- codec round trip


@pytest.mark.parametrize("size", [1, 31, 32, 33, 64, 150, 1000])
@pytest.mark.parametrize("direction", ["write", "read"])
def test_split_and_reassemble_round_trip(spec: ProtocolSpec, size: int, direction: str) -> None:
    mp = spec.multipart[0]
    layouts = mp.write if direction == "write" else mp.read
    assert layouts is not None
    data = bytes((i * 31) & 0xFF for i in range(size))
    packets = build_packets(mp, layouts, data, message_id=0x1234)
    assert len(packets) == -(-size // mp.max_data_per_packet)
    reasm = MultipartReassembler(mp, layouts)
    for body in packets:
        assert not reasm.complete
        reasm.add(body)
    assert reasm.complete and reasm.finish() == data
    assert reasm.message_id == 0x1234


def test_first_and_following_packets_use_their_own_layouts(spec: ProtocolSpec) -> None:
    mp = spec.multipart[0]
    assert mp.write is not None
    packets = build_packets(mp, mp.write, DATA, message_id=9)
    first = decode_packet(mp, mp.write.first, packets[0])
    assert first["packet_number"] == 0 and first["total_length"] == len(DATA) and first["message_id"] == 9
    assert len(packets[0]) == 2 + 2 + 4 + 2 + 1 + 32  # the obsolete byte is sent as zero
    assert packets[0][10] == 0
    later = decode_packet(mp, mp.write.layout(1), packets[1])
    assert later == {"packet_number": 1, "message_id": 9, "data": DATA[32:64]}


def test_every_packet_frame_round_trips_through_the_codec(spec: ProtocolSpec) -> None:
    mp = spec.multipart[0]
    assert mp.write is not None and mp.read is not None
    codec = FrameCodec(spec)
    for body in build_packets(mp, mp.write, DATA, 1):
        frames, rest = codec.extract_frames(codec.encode_command("write_certificate", {"packet": body}), direction="request")
        assert not rest and frames[0].ok and bytes.fromhex(frames[0].fields["packet"]) == body
    for body in build_packets(mp, mp.read, DATA, 1):
        frames, _ = codec.extract_frames(codec.encode_response("read_certificate", {"packet": body}), direction="response")
        assert frames[0].ok and bytes.fromhex(frames[0].fields["packet"]) == body


# ------------------------------------------------------------------------------------ reassembly errors


def _read_packets(spec: ProtocolSpec, data: bytes = DATA) -> List[bytes]:
    mp = spec.multipart[0]
    assert mp.read is not None
    return build_packets(mp, mp.read, data, message_id=5)


def _feed(spec: ProtocolSpec, packets: List[bytes], direction: str = "read") -> bytes:
    mp = spec.multipart[0]
    reasm = MultipartReassembler(mp, mp.read if direction == "read" else mp.write)  # type: ignore[arg-type]
    for body in packets:
        reasm.add(body)
    return reasm.finish()


def _patch(spec: ProtocolSpec, body: bytes, index: int, **roles: Any) -> bytes:
    """Re-encode one read packet with some role values replaced."""
    mp = spec.multipart[0]
    assert mp.read is not None
    layout = mp.read.layout(index)
    values = decode_packet(mp, layout, body)
    values.update(roles)
    return encode_layout(mp, layout, values)


def test_out_of_order_packets_are_reported(spec: ProtocolSpec) -> None:
    packets = _read_packets(spec)
    with pytest.raises(MultipartError, match="out of order: expected packet 2, received packet 1"):
        _feed(spec, [packets[0], packets[1], packets[1]])


def test_a_missing_packet_is_reported(spec: ProtocolSpec) -> None:
    packets = _read_packets(spec)
    with pytest.raises(MultipartError, match="packet 2 is missing: received packet 3"):
        _feed(spec, [packets[0], packets[1], packets[3]])


def test_too_few_packets_is_reported_on_finish(spec: ProtocolSpec) -> None:
    with pytest.raises(MultipartError, match="message incomplete"):
        _feed(spec, _read_packets(spec)[:-1])


def test_a_bad_per_packet_crc_is_reported(spec: ProtocolSpec) -> None:
    packets = _read_packets(spec)
    packets[0] = _patch(spec, packets[0], 0, packet_crc=0xBEEF)
    with pytest.raises(MultipartError, match="packet 0: packet CRC mismatch"):
        _feed(spec, packets)


def test_a_bad_running_crc_is_reported(spec: ProtocolSpec) -> None:
    packets = _read_packets(spec)
    packets[2] = _patch(spec, packets[2], 2, running_crc=0x0001)
    with pytest.raises(MultipartError, match="packet 2: running CRC mismatch"):
        _feed(spec, packets)


def test_a_bad_whole_message_crc_is_reported(spec: ProtocolSpec) -> None:
    mp = spec.multipart[0]
    assert mp.write is not None
    packets = build_packets(mp, mp.write, DATA, 3)
    values = decode_packet(mp, mp.write.first, packets[0])
    values["message_crc"] ^= 0xFFFF
    packets[0] = encode_layout(mp, mp.write.first, values)
    with pytest.raises(MultipartError, match="message CRC mismatch"):
        _feed(spec, packets, direction="write")


def test_a_message_id_mismatch_is_reported(spec: ProtocolSpec) -> None:
    packets = _read_packets(spec)
    packets[1] = _patch(spec, packets[1], 1, message_id=6)
    with pytest.raises(MultipartError, match="message id 6 differs from the first packet's 5"):
        _feed(spec, packets)


def test_a_data_length_field_that_disagrees_with_the_section_is_reported(spec: ProtocolSpec) -> None:
    data = copy.deepcopy(_raw(spec))
    first = data["multipart"][0]["write"]["first"]
    first.insert(5, {"name": "data_length", "type": "uint8"})  # the data is not length_ref'd, so the two can disagree
    patched = ProtocolSpec.model_validate(data)
    mp = patched.multipart[0]
    assert mp.write is not None
    packets = build_packets(mp, mp.write, DATA, 1)
    values = decode_packet(mp, mp.write.first, packets[0])
    packets[0] = encode_layout(mp, mp.write.first, {**values, "data_length": 3})
    reasm = MultipartReassembler(mp, mp.write)
    with pytest.raises(MultipartError, match="data length field says 3 byte"):
        reasm.add(packets[0])


def test_a_total_length_mismatch_is_reported(spec: ProtocolSpec) -> None:
    mp = spec.multipart[0]
    assert mp.read is not None
    packets = _read_packets(spec)
    values = decode_packet(mp, mp.read.first, packets[0])
    packets[0] = encode_layout(mp, mp.read.first, {**values, "total_length": 40})
    with pytest.raises(MultipartError, match="more than the total length 40"):
        _feed(spec, packets)


# ------------------------------------------------------------------------------- session over the link


async def _with_session(spec: ProtocolSpec, transport: Any, body: Any) -> Any:
    async with SerialSession(spec, transport) as session:
        return await body(session)


def test_multi_packet_write_then_read_through_the_simulated_device(spec: ProtocolSpec) -> None:
    progress: List[float] = []

    async def body(session: SerialSession) -> Any:
        written = await session.send("write_certificate", {"data": DATA}, on_progress=lambda p: progress.append(p.percent_complete))
        read = await session.send("read_certificate", {})
        return written, read

    written, read = asyncio.run(_with_session(spec, _transport(spec), body))
    assert written.ok, written.error
    assert written.fields == {"packets": 5, "total_length": len(DATA)}
    assert len(written.frames) == 5 and written.multipart["direction"] == "write"
    assert progress[-1] == 100.0 and progress == sorted(progress)
    assert read.ok, read.error
    assert bytes.fromhex(read.fields["data"]) == DATA and read.fields["packets"] == 5
    assert read.multipart["data"] == DATA


def test_transfer_progress_and_history_use_the_transfer_manager(spec: ProtocolSpec) -> None:
    async def body(session: SerialSession) -> Any:
        job = MultipartTransfer(spec, "write_certificate")
        outcome = await job.write(session, {"data": DATA})
        reader = MultipartTransfer(spec, "read_certificate")
        return job, outcome, reader, await reader.read(session)

    job, outcome, reader, read = asyncio.run(_with_session(spec, _transport(spec), body))
    assert outcome.ok and outcome.packets == 5 and outcome.progress.total_chunks == 5
    assert job.manager.history.get_records()[0].status is TransferState.COMPLETED
    assert read.ok and read.data == DATA and reader.progress.percent_complete == 100.0
    assert reader.manager.history.get_records()[0].status is TransferState.COMPLETED


def test_cancel_stops_before_the_next_packet(spec: ProtocolSpec) -> None:
    async def body(session: SerialSession) -> Any:
        job = MultipartTransfer(spec, "write_certificate")
        return await job.write(session, {"data": DATA}, on_progress=lambda p: job.cancel() if p.current_chunk >= 2 else None)

    outcome = asyncio.run(_with_session(spec, _transport(spec), body))
    assert outcome.state is TransferState.CANCELLED and outcome.packets == 2


def test_a_nak_ends_the_write_with_a_clear_device_error(spec: ProtocolSpec) -> None:
    transport = _transport(spec)
    nak = FrameCodec(spec).encode_message(0x7F, b"")
    transport.register_response(0x30, nak)

    async def body(session: SerialSession) -> Any:
        return await session.send("write_certificate", {"data": DATA})

    exchange = asyncio.run(_with_session(spec, transport, body))
    assert exchange.status is ExchangeStatus.DEVICE_ERROR
    assert "packet 0 of 5" in exchange.error and "NAK" in exchange.error


def test_the_simulated_device_naks_an_out_of_order_write_packet(spec: ProtocolSpec) -> None:
    mp = spec.multipart[0]
    assert mp.write is not None
    packets = build_packets(mp, mp.write, DATA, 2)

    async def body(session: SerialSession) -> Any:
        first = await session.send("write_certificate", {"packet": packets[0]}, multipart=False)
        skipped = await session.send("write_certificate", {"packet": packets[2]}, multipart=False)
        return first, skipped

    first, skipped = asyncio.run(_with_session(spec, _transport(spec), body))
    assert first.ok
    assert skipped.status is ExchangeStatus.DEVICE_ERROR


class _ScriptedTransport(VirtualTransport):
    """Answers each read request with the next prepared reply body (tampered on purpose)."""

    def __init__(self, spec: ProtocolSpec, replies: List[bytes]) -> None:
        super().__init__(spec, latency_ms=0.0, jitter_ms=0.0)
        self.replies = list(replies)
        self.codec = FrameCodec(spec)

    def _generate_response(self, request_bytes: bytes) -> bytes:
        return self.codec.encode_response("read_certificate", {"packet": self.replies.pop(0)}) if self.replies else b""


@pytest.mark.parametrize(
    "tamper, message",
    [
        (lambda p: [p[0], p[2], p[3], p[4]], "packet 1 is missing: received packet 2"),
        (lambda p: [p[0], p[1], p[1], p[3], p[4]], "out of order: expected packet 2, received packet 1"),
    ],
)
def test_a_read_with_a_gap_or_out_of_order_packet_fails_without_a_timeout(spec: ProtocolSpec, tamper: Any, message: str) -> None:
    transport = _ScriptedTransport(spec, tamper(_read_packets(spec)))

    async def body(session: SerialSession) -> Any:
        return await session.send("read_certificate", {})

    started = time.monotonic()
    exchange = asyncio.run(_with_session(spec, transport, body))
    assert exchange.status is ExchangeStatus.INVALID_RESPONSE
    assert message in exchange.error
    assert time.monotonic() - started < 0.9  # reported at once, not after the response timeout


def test_a_read_with_a_bad_packet_crc_fails(spec: ProtocolSpec) -> None:
    packets = _read_packets(spec)
    packets[0] = _patch(spec, packets[0], 0, packet_crc=0x1111)

    async def body(session: SerialSession) -> Any:
        return await session.send("read_certificate", {})

    exchange = asyncio.run(_with_session(spec, _ScriptedTransport(spec, packets), body))
    assert exchange.status is ExchangeStatus.INVALID_RESPONSE and "packet CRC mismatch" in exchange.error


def test_the_declarative_simulator_reassembles_writes_and_serves_reads(spec: ProtocolSpec) -> None:
    sim = BaseDeviceSimulator(spec)
    codec = FrameCodec(spec)
    mp = spec.multipart[0]
    assert mp.write is not None
    for body in build_packets(mp, mp.write, DATA, 4):
        reply = sim.process_incoming_bytes(bytearray(codec.encode_command("write_certificate", {"packet": body})))
        assert reply is not None
        frames, _ = codec.extract_frames(reply, direction="response")
        assert frames[0].kind == "response"
    reasm = MultipartReassembler(mp, mp.read)  # type: ignore[arg-type]
    while not reasm.complete:
        request = encode_layout(mp, mp.read.request_first or [], {"packet_number": reasm.index})  # type: ignore[union-attr]
        reply = sim.process_incoming_bytes(bytearray(codec.encode_command("read_certificate", {"request": request})))
        frames, _ = codec.extract_frames(reply or b"", direction="response")
        reasm.add(bytes.fromhex(frames[0].fields["packet"]))
    assert reasm.finish() == DATA


def test_read_only_sessions_refuse_multipart_writes(spec: ProtocolSpec) -> None:
    from omniuart.core.session import CommandBlockedError

    async def body() -> Any:
        async with SerialSession(spec, _transport(spec), read_only=True) as session:
            ok = await session.send("read_certificate", {})
            with pytest.raises(CommandBlockedError):
                await session.send("write_certificate", {"data": DATA})
            return ok

    assert asyncio.run(body()).ok


# ---------------------------------------------------------------------------------------- dissector


def test_dissector_shows_each_packet_header_field(spec: ProtocolSpec) -> None:
    mp = spec.multipart[0]
    assert mp.write is not None and mp.read is not None
    codec = FrameCodec(spec)
    first = dissect_frame(spec, codec.encode_command("write_certificate", {"packet": build_packets(mp, mp.write, DATA, 7)[0]}))
    names = [s.field_name for s in first.field_slices]
    assert first.multipart and first.multipart["layout"] == "first"
    for name in ("packet.packet_number", "packet.message_id", "packet.total_length", "packet.message_crc", "packet.reserved", "packet.data"):
        assert name in names
    later = dissect_frame(spec, codec.encode_command("write_certificate", {"packet": build_packets(mp, mp.write, DATA, 7)[3]}))
    assert later.multipart and later.multipart["layout"] == "next"
    assert next(s for s in later.field_slices if s.field_name == "packet.packet_number").decoded_value == 3
    reply = dissect_frame(spec, codec.encode_response("read_certificate", {"packet": _read_packets(spec)[0]}), direction="response")
    assert reply.multipart and reply.multipart["direction"] == "read"
    assert "packet.packet_crc" in [s.field_name for s in reply.field_slices]
    assert "Multipart : certificate" in reply.format_diagnostic_text()


# ---------------------------------------------------------------------------------------------- CLI


def test_cli_dry_run_reports_the_packets(spec: ProtocolSpec, capsys: pytest.CaptureFixture[str]) -> None:
    from omniuart.cli import main

    assert main(["--log-level", "ERROR", "send", "large_item_device", "write_certificate", "-p", "data=" + DATA.hex(), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Multipart : certificate (write, 5 packet(s))" in out and "first packet" in out
    request, count = first_request(spec, spec.get_command("write_certificate"), {"data": DATA})  # type: ignore[arg-type]
    assert count == 5 and request.hex(" ").upper() in out


def test_cli_send_writes_a_file_value_and_reads_an_item_to_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from omniuart.cli import main

    source = tmp_path / "cert.der"
    source.write_bytes(DATA)
    assert main(["--log-level", "ERROR", "send", "large_item_device", "write_certificate", "-p", f"data=@{source}", "--virtual"]) == 0
    assert "packets = 5" in capsys.readouterr().out
    target = tmp_path / "out.bin"
    assert main(["--log-level", "ERROR", "send", "large_item_device", "read_certificate", "--virtual", "-o", str(target)]) == 0
    assert target.read_bytes() and f"Saved     : {target.stat().st_size} bytes" in capsys.readouterr().out
    assert main(["--log-level", "ERROR", "send", "large_item_device", "ping", "--virtual", "-o", str(target)]) == 2


def test_cli_run_writes_and_reads_back_a_large_item(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from omniuart.cli import main

    script = {
        "version": "1.0.0",
        "meta": {"name": "large item round trip", "protocol": "large_item_device"},
        "steps": [
            {"name": "write", "command": "write_certificate", "params": {"data": DATA.hex()},
             "assertions": [{"field": "packets", "op": "==", "value": 5}]},
            {"name": "read", "command": "read_certificate",
             "assertions": [{"field": "data", "op": "==", "value": DATA.hex()}, {"field": "total_length", "op": "==", "value": len(DATA)}]},
        ],
    }
    path = tmp_path / "large_item_round_trip.yaml"
    path.write_text(yaml.safe_dump(script), encoding="utf-8")
    assert main(["--log-level", "ERROR", "run", str(path), "--virtual"]) == 0, capsys.readouterr()
    assert "PASSED" in capsys.readouterr().out


# ---------------------------------------------------------------------------------------- dashboard


def test_dashboard_renders_get_and_set_cards(spec: ProtocolSpec) -> None:
    from omniuart.dashboard_generator import generate_device_dashboard_html

    page = generate_device_dashboard_html(spec)
    assert page.count('class="transfer-card multipart-card') == 2
    assert 'data-mp-command="write_certificate" data-direction="write"' in page
    assert 'data-action="mp-save"' in page and "/multipart" in page


def test_dashboard_api_sets_and_gets_a_large_item_with_progress() -> None:
    from fastapi.testclient import TestClient

    from omniuart.ui.app import app

    def wait(client: TestClient, job_id: str) -> Dict[str, Any]:
        for _ in range(200):
            job = client.get(f"/api/device/large_item_device/transfer/{job_id}").json()
            if job["done"]:
                return job
            time.sleep(0.02)
        raise AssertionError("job did not finish")

    with TestClient(app) as client:
        try:
            assert client.post("/api/serial/connect", json={"port": "virtual", "protocol": "large_item_device"}).status_code == 200
            body = {"command": "write_certificate", "data_base64": base64.b64encode(DATA).decode()}
            started = client.post("/api/device/large_item_device/multipart", json=body)
            assert started.status_code == 200, started.text
            job = wait(client, started.json()["job_id"])
            assert job["state"] == "completed" and job["kind"] == "multipart_write" and job["packets"] == 5
            assert job["progress"]["percent_complete"] == 100.0

            started = client.post("/api/device/large_item_device/multipart", json={"command": "read_certificate"})
            job = wait(client, started.json()["job_id"])
            assert job["state"] == "completed" and base64.b64decode(job["data_base64"]) == DATA

            assert client.post("/api/device/large_item_device/multipart", json={"command": "ping"}).status_code == 422
            assert client.post("/api/device/large_item_device/multipart", json={"command": "write_certificate"}).status_code == 422
            state = client.get("/api/device/large_item_device/state").json()
            assert len(state["exchanges"]) >= 10  # every packet is in the Engineer view
        finally:
            client.post("/api/serial/disconnect")


def test_plain_command_send_route_summarises_a_multipart_read() -> None:
    from fastapi.testclient import TestClient

    from omniuart.ui.app import app

    with TestClient(app) as client:
        try:
            client.post("/api/serial/connect", json={"port": "virtual", "protocol": "large_item_device"})
            r = client.post("/api/send/large_item_device", json={"command": "read_certificate", "params": {}})
            assert r.status_code == 200, r.text
        finally:
            client.post("/api/serial/disconnect")
