"""Every fuzz outcome is reachable and reported correctly (#191)."""

import pytest

from omniuart.cli import main as cli_main
from omniuart.core.codec import FrameCodec
from omniuart.core.fuzzer import FuzzOutcome, ProtocolFuzzer
from omniuart.core.models import load_protocol
from omniuart.core.transport import AsyncTransport, VirtualTransport

SPEC_YAML = """
schema_version: "1.0.0"
metadata: {name: F, version: "1.0.0"}
serial_config: {baudrate: 115200}
framing:
  type: binary
  header: [0xAA, 0x55]
  length: {type: uint8}
  command_id: {type: uint8}
  integrity: {algorithm: crc16_modbus}
commands:
  - name: read
    id: 1
    parameters: [{name: ch, type: uint8, min: 0, max: 3, default: 0}]
    response:
      id: 0x81
      fields: [{name: v, type: uint8, default: 7}]
"""


@pytest.fixture()
def spec():
    return load_protocol(SPEC_YAML)


class FakeDevice(AsyncTransport):
    """Scriptable device: ``behaviour(request) -> bytes`` decides what it sends back."""

    def __init__(self, behaviour, fail_write=False):
        self.behaviour = behaviour
        self.fail_write = fail_write
        self._buf = bytearray()
        self._open = True

    async def open(self): self._open = True
    async def close(self): self._open = False
    async def set_pin_state(self, pin, state): pass

    @property
    def is_open(self): return self._open

    async def write(self, data):
        if self.fail_write:
            raise OSError("port vanished")
        self._buf.extend(self.behaviour(bytes(data)))
        return len(data)

    async def read(self, size=1, timeout_ms=1000):
        out = bytes(self._buf[:size])
        del self._buf[:size]
        return out


def outcomes(report):
    return {(r.vector.strategy, r.status) for r in report.results}


@pytest.mark.asyncio
async def test_compliant_device_is_accepted_and_correctly_rejects(spec):
    transport = VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0)
    report = await ProtocolFuzzer(spec, seed=3).run_campaign(transport, timeout_ms=50)
    got = outcomes(report)
    assert ("valid", FuzzOutcome.ACCEPTED) in got
    assert ("out_of_bounds", FuzzOutcome.CORRECTLY_REJECTED) in got
    assert ("corrupted_integrity", FuzzOutcome.CORRECTLY_REJECTED) in got
    assert ("truncated_frame", FuzzOutcome.CORRECTLY_REJECTED) in got
    assert report.passed and report.handled_count == report.total_vectors


@pytest.mark.asyncio
async def test_device_that_answers_everything_is_unexpectedly_accepted(spec):
    codec = FrameCodec(spec)
    transport = FakeDevice(lambda req: codec.encode_response("read"))
    report = await ProtocolFuzzer(spec, seed=1).run_campaign(transport, timeout_ms=20)
    assert FuzzOutcome.UNEXPECTEDLY_ACCEPTED.value in report.outcomes
    assert report.unexpected_count >= 3 and not report.passed


@pytest.mark.asyncio
async def test_garbage_is_a_malformed_response(spec):
    transport = FakeDevice(lambda req: b"\xde\xad\xbe\xef")
    report = await ProtocolFuzzer(spec, seed=1).run_campaign(transport, timeout_ms=20)
    assert report.malformed_count == report.total_vectors and not report.passed


@pytest.mark.asyncio
async def test_silent_device_times_out_on_valid_requests_only(spec):
    transport = FakeDevice(lambda req: b"")
    report = await ProtocolFuzzer(spec, seed=1).run_campaign(transport, timeout_ms=20)
    by = {(r.vector.strategy): r.status for r in report.results}
    assert by["valid"] is FuzzOutcome.TIMEOUT
    # Invalid requests are silently ignored, but the probe afterwards shows the device is dead.
    assert by["corrupted_integrity"] is FuzzOutcome.HANG
    assert report.hang_count == report.total_vectors and not report.passed


@pytest.mark.asyncio
async def test_device_that_locks_up_after_a_bad_frame_is_a_hang(spec):
    codec = FrameCodec(spec)
    state = {"dead": False}

    def behaviour(req):
        if state["dead"]:
            return b""
        frames, _ = codec.extract_frames(req, direction="request")
        if not frames or not frames[0].ok:
            state["dead"] = True  # firmware wedges on the first invalid frame
            return b""
        return codec.encode_response("read")

    report = await ProtocolFuzzer(spec, seed=1).run_campaign(FakeDevice(behaviour), timeout_ms=20)
    statuses = [r.status for r in report.results]
    assert statuses[0] is FuzzOutcome.ACCEPTED
    assert FuzzOutcome.HANG in statuses


@pytest.mark.asyncio
async def test_transport_failure_is_reported_not_swallowed(spec):
    report = await ProtocolFuzzer(spec).run_campaign(FakeDevice(lambda r: b"", fail_write=True), timeout_ms=20)
    assert report.crash_count == report.total_vectors
    assert all("port vanished" in r.detail for r in report.results)


@pytest.mark.asyncio
async def test_only_applicable_strategies_are_generated():
    spec = load_protocol(SPEC_YAML.replace("integrity: {algorithm: crc16_modbus}", "integrity: {algorithm: none}").replace(
        "parameters: [{name: ch, type: uint8, min: 0, max: 3, default: 0}]", "parameters: []"))
    strategies = {v.strategy for v in ProtocolFuzzer(spec).generate_vectors_for_command(spec.commands[0])}
    assert strategies == {"valid", "truncated_frame", "random_mutation"}


def test_vectors_are_valid_frames_built_by_the_codec(spec):
    codec = FrameCodec(spec)
    vectors = {v.strategy: v for v in ProtocolFuzzer(spec, seed=5).generate_vectors_for_command(spec.commands[0])}
    assert codec.decode(vectors["valid"].raw_payload, direction="request").ok
    assert vectors["corrupted_integrity"].expected_failure
    assert "integrity mismatch" in codec.decode(vectors["corrupted_integrity"].raw_payload, direction="request").error
    oob = codec.decode(vectors["out_of_bounds"].raw_payload, direction="request")
    assert oob.ok and oob.fields == {"ch": 4}  # well formed on the wire, outside the declared range


def test_cli_fuzz_exit_code_reflects_the_result(capsys):
    assert cli_main(["fuzz", "binary_sensor_node", "-n", "8"]) == 0
    assert "Handled correctly" in capsys.readouterr().out
