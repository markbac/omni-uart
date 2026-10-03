"""CLI send transmits a real frame and reports the decoded response (#192)."""

import pytest

from omniuart.cli import main as cli_main
from omniuart.core.codec import FrameCodec
from omniuart.core.catalog import CatalogManager
from omniuart.core.models import load_protocol
from omniuart.core.session import DeviceSession, ExchangeStatus
from omniuart.core.simulator import BaseDeviceSimulator
from omniuart.core.transport import VirtualSerialPair, VirtualTransport


def test_send_to_virtual_device_decodes_the_response(capsys):
    assert cli_main(["send", "binary_sensor_node", "get_readings", "-p", "channel=2", "--virtual"]) == 0
    out = capsys.readouterr().out
    assert "Request   : AA 55 01 00 02 02" in out
    assert "Response  : AA 55" in out
    assert "channel = 0" in out and "temperature = " in out
    assert "Status    : OK" in out


def test_send_without_a_transport_is_an_error_not_a_fake_success(capsys):
    assert cli_main(["send", "binary_sensor_node", "ping"]) == 2
    assert "--dry-run" in capsys.readouterr().err


def test_send_rejects_invalid_parameters_before_transmitting(capsys):
    assert cli_main(["send", "binary_sensor_node", "get_readings", "-p", "channel=99", "--virtual"]) == 2
    assert "above the maximum" in capsys.readouterr().err


def test_send_reports_timeout_with_nonzero_exit(capsys):
    # Loopback echoes the request, which is not a valid response, so the exchange must fail.
    assert cli_main(["send", "binary_sensor_node", "ping", "--port", "loop://", "--timeout", "100"]) == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.err


def test_send_to_missing_serial_port_is_a_transport_error(capsys):
    assert cli_main(["send", "binary_sensor_node", "ping", "--port", "/dev/omniuart-does-not-exist"]) == 3


def test_send_unknown_command(capsys):
    assert cli_main(["send", "binary_sensor_node", "nope", "--virtual"]) == 1


@pytest.fixture()
def spec():
    return CatalogManager().get_protocol("binary_sensor_node")


@pytest.mark.asyncio
async def test_session_times_out_when_the_device_is_silent(spec):
    pair = VirtualSerialPair()
    await pair.open()
    async with DeviceSession(spec, pair.host) as session:
        exchange = await session.send("ping", timeout_ms=50)
    assert exchange.status is ExchangeStatus.TIMEOUT and not exchange.ok
    await pair.close()


@pytest.mark.asyncio
async def test_session_reports_a_corrupt_response(spec):
    pair = VirtualSerialPair()
    await pair.open()
    codec = FrameCodec(spec)

    class Corrupting(BaseDeviceSimulator):
        def handle_frame(self, frame):
            good = bytearray(super().handle_frame(frame))
            good[-4] ^= 0xFF
            return bytes(good)

    sim = Corrupting(spec=spec, transport=pair.device, latency_ms=0)
    await sim.start()
    try:
        async with DeviceSession(spec, pair.host) as session:
            exchange = await session.send("ping", timeout_ms=500)
        assert exchange.status is ExchangeStatus.INVALID_RESPONSE
        assert "integrity mismatch" in exchange.error
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_session_records_both_directions(spec):
    from omniuart.core.recorder import SessionRecorder

    recorder = SessionRecorder()
    transport = VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0)
    async with DeviceSession(spec, transport, recorder=recorder) as session:
        exchange = await session.send("get_readings", {"channel": 1})
    assert exchange.ok and exchange.response.name == "get_readings"
    assert [e.direction for e in recorder.events] == ["tx", "rx"]
    assert recorder.events[0].decoded_fields == {"channel": 1}
    assert "temperature" in recorder.events[1].decoded_fields


@pytest.mark.asyncio
async def test_command_without_response_does_not_wait():
    spec = load_protocol(
        """
schema_version: "1.0.0"
metadata: {name: N, version: "1.0.0"}
serial_config: {baudrate: 9600}
framing: {type: binary, header: [0xAA], command_id: {type: uint8}}
commands: [{name: fire, id: 1}]
"""
    )
    transport = VirtualTransport(spec, latency_ms=1.0, jitter_ms=0.0)
    async with DeviceSession(spec, transport) as session:
        exchange = await session.send("fire")
    assert exchange.ok and exchange.response is None
