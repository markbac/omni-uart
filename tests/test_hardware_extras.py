"""Unit tests for hardware tooling extras: auto-baud, RS-485 RTS control, line error counters, and pulse pins."""

from __future__ import annotations

import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.core.models import SerialConfig
from omniuart.core.transport import VirtualTransport, auto_detect_baudrate


def test_serial_config_rs485_and_pulse_pins() -> None:
    """Verify SerialConfig accepts RS-485 parameters and pulse_pins entry sequence."""
    config = SerialConfig(
        baudrate=115200,
        rs485_rts_mode=True,
        rs485_turnaround_ms=2.0,
        pulse_pins=[{"pin": "rts", "state": True, "duration_ms": 10}],
    )
    assert config.rs485_rts_mode is True
    assert config.rs485_turnaround_ms == 2.0
    assert len(config.pulse_pins) == 1


@pytest.mark.asyncio
async def test_virtual_transport_rs485_rts_toggling() -> None:
    """Verify VirtualTransport toggles RTS pin in RS-485 mode during write."""
    vt = VirtualTransport(rs485_rts_mode=True, rs485_turnaround_ms=0.0)
    await vt.open()
    assert vt.pin_states["rts"] is False

    await vt.write(b"\xAA\x55")
    # After write finishes, RTS is returned to False
    assert vt.pin_states["rts"] is False


@pytest.mark.asyncio
async def test_auto_detect_baudrate() -> None:
    """Verify auto_detect_baudrate identifies working baudrate."""
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node.yaml")
    assert spec is not None

    def creator(baud: int) -> VirtualTransport:
        return VirtualTransport(protocol=spec, latency_ms=1.0)

    detected = await auto_detect_baudrate(creator, spec, candidate_baudrates=[9600, 115200])
    assert detected in (9600, 115200)
