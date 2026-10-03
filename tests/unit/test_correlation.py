"""Request/response correlation by command, field values or a custom predicate (#198)."""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from omniuart.core.codec import FrameCodec
from omniuart.core.models import load_protocol
from omniuart.core.session import DeviceSession, ExchangeStatus
from omniuart.core.simulator import BaseDeviceSimulator
from omniuart.core.transport import VirtualSerialPair

SPEC = """
schema_version: "1.0.0"
metadata: {name: Corr, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing:
  type: binary
  header: [0xAA]
  length: {type: uint8, includes: payload_only}
  command_id: {type: uint8}
  integrity: {algorithm: crc16_modbus}
correlate: [tid]
commands:
  - name: read
    id: 1
    safety: read_only
    parameters: [{name: tid, type: uint8, default: 0}]
    response:
      id: 0x81
      timeout_ms: 300
      fields: [{name: tid, type: uint8}, {name: value, type: uint16, default: 7}]
  - name: ping
    id: 2
    safety: read_only
    response: {id: 0x82, timeout_ms: 300, fields: [{name: ok, type: uint8, default: 1}]}
telemetry:
  - {name: tick, id: 0x90, fields: [{name: n, type: uint8, default: 1}]}
"""


class Scripted(BaseDeviceSimulator):
    """Answers a request with whatever frames ``script(request_fields)`` returns."""

    def __init__(self, spec, transport, script):
        super().__init__(spec=spec, transport=transport, latency_ms=0)
        self.script = script

    def handle_frame(self, frame):
        codec = self.codec
        out = b""
        for kind, name, values in self.script(frame.fields):
            out += codec.encode_response(name, values) if kind == "response" else codec.encode_telemetry(name, values)
        return out


async def exchange(script, command="read", params=None, **session_kwargs):
    spec = load_protocol(SPEC)
    pair = VirtualSerialPair()
    await pair.open()
    sim = Scripted(spec, pair.device, script)
    await sim.start()
    try:
        session = DeviceSession(spec, pair.host, **session_kwargs)
        return await session.send(command, {"tid": 5} if params is None else params, timeout_ms=300)
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_response_with_matching_transaction_id_is_accepted() -> None:
    result = await exchange(lambda req: [("response", "read", {"tid": req["tid"], "value": 42})])
    assert result.ok and result.fields == {"tid": 5, "value": 42} and result.unsolicited == []


@pytest.mark.asyncio
async def test_stale_response_is_skipped_and_the_right_one_is_used() -> None:
    result = await exchange(lambda req: [("response", "read", {"tid": 4, "value": 1}), ("response", "read", {"tid": req["tid"], "value": 2})])
    assert result.ok and result.fields["value"] == 2
    assert [f.fields["tid"] for f in result.unsolicited] == [4]


@pytest.mark.asyncio
async def test_only_a_stale_response_is_a_timeout_not_an_answer() -> None:
    result = await exchange(lambda req: [("response", "read", {"tid": 99, "value": 1})])
    assert result.status is ExchangeStatus.TIMEOUT and "no matching response" in result.error
    assert result.response is None and len(result.unsolicited) == 1


@pytest.mark.asyncio
async def test_unsolicited_telemetry_is_reported_and_does_not_end_the_wait() -> None:
    seen = []
    result = await exchange(
        lambda req: [("telemetry", "tick", {"n": 3}), ("response", "read", {"tid": req["tid"], "value": 9})],
        on_unsolicited=seen.append,
    )
    assert result.ok and result.fields["value"] == 9
    assert [f.name for f in result.unsolicited] == ["tick"] and [f.name for f in seen] == ["tick"]


@pytest.mark.asyncio
async def test_commands_without_the_correlation_fields_are_not_affected() -> None:
    result = await exchange(lambda req: [("response", "ping", {"ok": 1})], command="ping", params={})
    assert result.ok and result.fields == {"ok": 1}


@pytest.mark.asyncio
async def test_custom_matcher_replaces_the_default_rule() -> None:
    result = await exchange(
        lambda req: [("response", "read", {"tid": 1, "value": 10}), ("response", "read", {"tid": 1, "value": 77})],
        matcher=lambda cmd, sent, frame: frame.fields.get("value") == 77,
    )
    assert result.ok and result.fields["value"] == 77 and len(result.unsolicited) == 1


def test_correlate_fields_must_exist_in_parameters_and_response() -> None:
    bad = yaml.safe_load(SPEC)
    bad["commands"][0]["correlate"] = ["nope"]
    with pytest.raises(ValidationError, match="correlate field 'nope'"):
        load_protocol(yaml.safe_dump(bad))
    no_response = yaml.safe_load(SPEC)
    no_response["commands"][0].pop("response")
    no_response["commands"][0]["correlate"] = ["tid"]
    with pytest.raises(ValidationError, match="no response"):
        load_protocol(yaml.safe_dump(no_response))


def test_protocol_default_applies_only_where_all_fields_exist() -> None:
    spec = load_protocol(SPEC)
    assert spec.correlation_fields(spec.get_command("read")) == ["tid"]
    assert spec.correlation_fields(spec.get_command("ping")) == []
    assert FrameCodec(spec)  # still a valid protocol
