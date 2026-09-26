"""Unit tests for virtual device simulators (AT modem, IoT sensor node, Modbus RTU)."""

from __future__ import annotations

import asyncio
import pytest
from omniuart.core.simulator import (
    ATModemSimulator,
    BaseDeviceSimulator,
    IoTSensorSimulator,
    ModbusRtuSimulator,
)
from omniuart.core.transport import VirtualSerialPair


@pytest.mark.asyncio
async def test_at_modem_simulator() -> None:
    pair = VirtualSerialPair()
    await pair.open()

    sim = ATModemSimulator(transport=pair.device)
    await sim.start()

    try:
        # Test AT ping
        await pair.host.write(b"AT\r\n")
        resp = await pair.host.read(size=4, timeout_ms=500)
        assert b"OK" in resp

        # Test AT+CSQ signal quality query
        await pair.host.write(b"AT+CSQ\r\n")
        resp_csq = await pair.host.read(size=20, timeout_ms=500)
        assert b"+CSQ:" in resp_csq
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_iot_sensor_simulator_telemetry() -> None:
    pair = VirtualSerialPair()
    await pair.open()

    sim = IoTSensorSimulator(transport=pair.device, telemetry_interval_sec=0.1)
    await sim.start()

    try:
        # Read incoming periodic telemetry frame on host side
        telemetry_bytes = await pair.host.read(size=8, timeout_ms=1000)
        assert len(telemetry_bytes) == 8
        assert telemetry_bytes[0] == 0x55
        assert telemetry_bytes[1] == 0xAA
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_modbus_rtu_simulator() -> None:
    sim = ModbusRtuSimulator(slave_address=1)
    # Test function 0x03 holding register read logic directly
    request_frame = bytearray([0x01, 0x03, 0x00, 0x00, 0x00, 0x02, 0xC4, 0x0B])
    resp = sim.process_incoming_bytes(request_frame)
    assert resp is not None
    assert resp[0] == 0x01
    assert resp[1] == 0x03
    assert resp[2] == 0x04  # Byte count for 2 holding registers (4 bytes)
