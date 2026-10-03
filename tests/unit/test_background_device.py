"""Headless tests for the thread-safe device controller used by the desktop GUI."""

from __future__ import annotations

import pytest

from omniuart.core.background import BackgroundDevice, NotConnected, VIRTUAL_PORT, is_safe_poll_command
from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import CodecError
from omniuart.core.models import ProtocolSpec, ScriptSpec
from omniuart.core.session import ExchangeStatus


@pytest.fixture()
def spec() -> ProtocolSpec:
    loaded = CatalogManager().get_protocol("binary_sensor_node")
    assert loaded is not None
    return loaded


@pytest.fixture()
def device():
    dev = BackgroundDevice()
    yield dev
    dev.close()


def test_send_requires_a_connection(device: BackgroundDevice, spec: ProtocolSpec) -> None:
    with pytest.raises(NotConnected):
        device.send(spec, "get_readings", {"channel": 1}).result(timeout=5)
    assert device.connected is False


def test_connect_failure_is_raised_and_leaves_device_disconnected(device: BackgroundDevice) -> None:
    with pytest.raises(Exception):
        device.connect("/dev/does-not-exist", 115200).result(timeout=5)
    assert device.connected is False


def test_virtual_send_returns_a_decoded_response(device: BackgroundDevice, spec: ProtocolSpec) -> None:
    device.connect(VIRTUAL_PORT, 115200).result(timeout=5)
    assert device.connected and device.simulated
    exchange = device.send(spec, "get_readings", {"channel": 1}).result(timeout=5)
    assert exchange.status is ExchangeStatus.OK
    assert exchange.response is not None and exchange.response.fields


def test_invalid_parameters_raise_before_transmit(device: BackgroundDevice, spec: ProtocolSpec) -> None:
    device.connect(VIRTUAL_PORT, 115200).result(timeout=5)
    with pytest.raises(CodecError):
        device.send(spec, "get_readings", {"channel": 9999}).result(timeout=5)


def test_disconnect_closes_the_link(device: BackgroundDevice, spec: ProtocolSpec) -> None:
    device.connect(VIRTUAL_PORT, 115200).result(timeout=5)
    device.disconnect().result(timeout=5)
    assert device.connected is False
    with pytest.raises(NotConnected):
        device.send(spec, "get_readings", {"channel": 1}).result(timeout=5)


def test_real_transport_over_loopback_url_times_out_honestly(device: BackgroundDevice, spec: ProtocolSpec) -> None:
    """A loop:// port echoes the request, which is not a valid response, so the exchange must not pass."""
    device.connect("loop://", 115200).result(timeout=5)
    assert device.connected and not device.simulated
    exchange = device.send(spec, "get_readings", {"channel": 1}, timeout_ms=200).result(timeout=5)
    assert exchange.status is not ExchangeStatus.OK


def test_script_runs_with_real_pass_fail(device: BackgroundDevice, spec: ProtocolSpec) -> None:
    device.connect(VIRTUAL_PORT, 115200).result(timeout=5)
    script = ScriptSpec.model_validate(
        {
            "meta": {"name": "t", "protocol": "binary_sensor_node"},
            "steps": [
                {"command": "get_readings", "params": {"channel": 1}},
                {"command": "get_readings", "params": {"channel": 1}, "assertions": [{"field": "no_such_field", "op": "==", "value": 1}]},
            ],
        }
    )
    seen = []
    result = device.run_script(script, spec, on_step=seen.append).result(timeout=10)
    assert [s.status.value for s in result.steps][0] == "passed"
    assert result.steps[1].status.value == "failed"
    assert len(seen) == 2 and not result.passed


def test_safe_poll_commands_are_dashboard_tagged_with_defaulted_params(spec: ProtocolSpec) -> None:
    for cmd in spec.commands:
        if is_safe_poll_command(cmd):
            assert "dashboard" in cmd.tags and cmd.response is not None
            assert all(p.default is not None for p in cmd.parameters)
        elif "dashboard" not in cmd.tags:
            assert not is_safe_poll_command(cmd)
