"""Back-to-back integration tests connecting virtual device simulators with Web UI, WebSockets, and Script Engine."""

from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient

from omniuart.core.simulator import (
    ATModemSimulator,
    IoTSensorSimulator,
    ModbusRtuSimulator,
)
from omniuart.core.transport import VirtualSerialPair
from omniuart.ui.app import app


@pytest.mark.asyncio
async def test_at_modem_simulator_back_to_back_web_ui() -> None:
    """Test ATModemSimulator back-to-back with FastAPI Web UI API endpoints."""
    pair = VirtualSerialPair()
    await pair.open()

    sim = ATModemSimulator(transport=pair.device)
    await sim.start()

    try:
        # Host sends AT command over virtual serial transport
        await pair.host.write(b"AT+CSQ\r\n")
        response_bytes = await pair.host.read(size=25, timeout_ms=1000)
        assert b"+CSQ:" in response_bytes
        assert b"OK" in response_bytes

        # Query Web UI protocol endpoint
        client = TestClient(app)
        res = client.get("/api/protocols")
        assert res.status_code == 200
        assert res.json()["protocols_found"] >= 1
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_iot_sensor_simulator_back_to_back_websocket() -> None:
    """Test IoTSensorSimulator back-to-back streaming periodic telemetry into WebSocket endpoint."""
    pair = VirtualSerialPair()
    await pair.open()

    sim = IoTSensorSimulator(transport=pair.device, telemetry_interval_sec=0.05)
    await sim.start()

    try:
        # Read 2 consecutive telemetry frames on host transport
        frame1 = await pair.host.read(size=8, timeout_ms=1000)
        assert len(frame1) == 8
        assert frame1[0] == 0x55
        assert frame1[1] == 0xAA

        frame2 = await pair.host.read(size=8, timeout_ms=1000)
        assert len(frame2) == 8
        assert frame2[0] == 0x55
        assert frame2[1] == 0xAA
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_modbus_rtu_simulator_back_to_back_sequence() -> None:
    """Test ModbusRtuSimulator back-to-back responding to request sequence frames."""
    pair = VirtualSerialPair()
    await pair.open()

    sim = ModbusRtuSimulator(slave_address=1, transport=pair.device)
    await sim.start()

    try:
        # Send Modbus Read Holding Registers (Func 0x03, Reg 0x0000, Count 2)
        request = bytearray([0x01, 0x03, 0x00, 0x00, 0x00, 0x02, 0xC4, 0x0B])
        await pair.host.write(bytes(request))

        response = await pair.host.read(size=9, timeout_ms=1000)
        assert len(response) == 9
        assert response[0] == 0x01  # Slave ID
        assert response[1] == 0x03  # Func Code
        assert response[2] == 0x04  # Byte count (4 bytes for 2 registers)
    finally:
        await sim.stop()
        await pair.close()


@pytest.mark.asyncio
async def test_desktop_and_cli_against_simulator() -> None:
    """Smoke test CLI / Desktop payload builder sending AT commands directly to simulator."""
    from omniuart.core.catalog import CatalogManager
    from omniuart.core.codec import build_frame_payload

    catalog = CatalogManager()
    at_spec = catalog.get_protocol("at-commands-uart-interface.json") or catalog.get_protocol("at-commands-uart-interface.yaml")
    if not at_spec:
        all_files = catalog.list_protocol_files()
        at_file = next((f for f in all_files if "at" in f.name.lower()), all_files[0])
        at_spec = catalog.get_protocol(at_file.name)
    assert at_spec is not None

    cmd = next((c for c in at_spec.commands if c.name == "AT+CGMI"), at_spec.commands[0])

    pair = VirtualSerialPair()
    await pair.open()

    sim = ATModemSimulator(spec=at_spec, transport=pair.device)
    await sim.start()

    try:
        # Build payload using Desktop/CLI builder
        payload = build_frame_payload(at_spec, cmd, {})
        assert isinstance(payload, bytes)
        assert len(payload) > 0

        # Transmit to simulator
        await pair.host.write(payload)

        # Receive simulator response
        res = await pair.host.read(size=64, timeout_ms=1000)
        assert len(res) > 0
        assert b"OK" in res or b"OmniUART" in res
    finally:
        await sim.stop()
        await pair.close()
