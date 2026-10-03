"""Resource and input safety limits (#211)."""

from __future__ import annotations

import asyncio
import json
import time

import pytest
import yaml

from omniuart.core.codec import FrameCodec
from omniuart.core.fuzzer import ProtocolFuzzer
from omniuart.core.limits import Limits, get_limits
from omniuart.core.models import load_protocol, load_script
from omniuart.core.replayer import SessionReplayer
from omniuart.core.runner import ScriptRunner, StepStatus
from omniuart.core.telemetry import TelemetryBridge
from omniuart.core.transport import VirtualTransport
from tests.unit.test_schema_simulator import LAYOUTS


def test_defaults_and_environment_overrides(monkeypatch) -> None:
    assert get_limits() == Limits()
    monkeypatch.setenv("OMNIUART_MAX_FRAME_BYTES", "4096")
    monkeypatch.setenv("OMNIUART_MAX_SCRIPT_DURATION_S", "2.5")
    assert (get_limits().frame_bytes, get_limits().script_duration_s) == (4096, 2.5)


@pytest.mark.parametrize("bad", ["0", "-5", "lots", ""])
def test_invalid_override_is_ignored_not_unlimited(monkeypatch, bad) -> None:
    monkeypatch.setenv("OMNIUART_MAX_FRAME_BYTES", bad)
    assert get_limits().frame_bytes == Limits().frame_bytes


def test_oversized_definition_file_and_text_are_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OMNIUART_MAX_DEFINITION_BYTES", "200")
    big = tmp_path / "big.yaml"
    big.write_text("metadata: {name: x, version: '1'}\n" + "# padding\n" * 100)
    with pytest.raises(ValueError, match="byte limit"):
        load_protocol(big)
    with pytest.raises(ValueError, match="byte limit"):
        load_script("# x\n" * 100)


@pytest.mark.parametrize("text", ["[" * 100_000, "[" * 100_000 + "]" * 100_000, '{"a":' * 100_000])
def test_deeply_nested_documents_are_a_value_error_not_a_crash(text) -> None:
    with pytest.raises(ValueError):
        load_protocol(text)


def test_absurd_field_length_is_rejected() -> None:
    doc = yaml.safe_load(LAYOUTS["header_length_crc_footer"])
    doc["commands"][0]["parameters"][0] = {"name": "blob", "type": "bytes", "length": 2_000_000_000}
    with pytest.raises(ValueError, match="field length"):
        load_protocol(yaml.safe_dump(doc))


def test_script_step_limit(monkeypatch) -> None:
    monkeypatch.setenv("OMNIUART_MAX_SCRIPT_STEPS", "3")
    steps = [{"log": "x"}] * 4
    with pytest.raises(ValueError, match="steps"):
        load_script(yaml.safe_dump({"meta": {"name": "s", "protocol": "p"}, "steps": steps}))
    load_script(yaml.safe_dump({"meta": {"name": "s", "protocol": "p"}, "steps": steps[:3]}))


def test_declared_frame_length_beyond_limit_is_not_waited_for(monkeypatch) -> None:
    monkeypatch.setenv("OMNIUART_MAX_FRAME_BYTES", "64")
    spec = load_protocol(LAYOUTS["header_length_crc_footer"])  # header AA 55, uint16 length
    codec = FrameCodec(spec)
    good = codec.encode_command("read", {})
    lying = b"\xAA\x55\xFF\xFF" + b"\x00" * 10
    frames, rest = codec.extract_frames(lying + good, direction="request")
    assert [f.raw for f in frames if f.ok] == [good]
    assert len(rest) < 64


def test_script_duration_limit_stops_the_run() -> None:
    from omniuart.core.models import ScriptSpec

    script = ScriptSpec.model_validate({"meta": {"name": "slow", "protocol": "p"}, "steps": [{"delay_ms": 60}] * 6})
    result = asyncio.run(ScriptRunner(script, session=None, max_duration_s=0.1).run())  # type: ignore[arg-type]
    statuses = [s.status for s in result.steps]
    assert StepStatus.ERROR in statuses and "duration limit" in result.steps[statuses.index(StepStatus.ERROR)].message
    assert statuses[-1] is StepStatus.SKIPPED


def test_replay_duration_limit(tmp_path) -> None:
    log = tmp_path / "s.jsonl"
    events = [
        {"timestamp": 1000.0 + i * 0.05, "direction": "tx", "raw_hex": "AA", "length_bytes": 1} for i in range(10)
    ]
    log.write_text("\n".join(json.dumps(e) for e in events))
    transport = VirtualTransport(latency_ms=0)
    started = time.monotonic()
    count = asyncio.run(SessionReplayer(transport, max_duration_s=0.12).replay_file(log))
    assert 1 <= count < 10 and time.monotonic() - started < 1.0


def test_fuzz_campaign_size_is_capped(monkeypatch) -> None:
    monkeypatch.setenv("OMNIUART_MAX_FUZZ_VECTORS", "2")
    fuzzer = ProtocolFuzzer(load_protocol(LAYOUTS["header_length_crc_footer"]), seed=1)
    assert len(fuzzer.select_vectors(1_000_000)) == 2


def test_retries_are_capped(monkeypatch) -> None:
    monkeypatch.setenv("OMNIUART_MAX_RETRIES", "3")
    assert TelemetryBridge(webhook_url="http://x", retries=10_000).retries == 3
