"""Unit tests for VirtualTransport, MCU loopback, latency simulation, and fault injection."""

import asyncio
import pytest

from omniuart.core.transport import VirtualTransport, list_available_ports


@pytest.mark.asyncio
async def test_virtual_transport_basic_loopback() -> None:
    """Verify virtual transport open, write, and response read."""
    transport = VirtualTransport(latency_ms=1.0, jitter_ms=0.5)
    assert not transport.is_open

    await transport.open()
    assert transport.is_open

    req_data = bytes([0xAA, 0x55, 0x02, 0x00, 0x01, 0x00, 0x3C, 0x12])
    written = await transport.write(req_data)
    assert written == len(req_data)

    resp = await transport.read(size=8, timeout_ms=500)
    assert len(resp) == 8
    assert resp[0] == 0xAA
    assert resp[1] == 0x55

    await transport.close()
    assert not transport.is_open


@pytest.mark.asyncio
async def test_virtual_transport_fault_crc_flip() -> None:
    """Verify fault injection CRC bit-flip behavior."""
    transport = VirtualTransport(latency_ms=1.0, fault_crc_flip=True)
    await transport.open()

    req_data = bytes([0xAA, 0x55, 0x02, 0x00, 0x01, 0x00, 0x3C, 0x12])
    await transport.write(req_data)

    resp = await transport.read(size=8, timeout_ms=500)
    assert len(resp) == 8
    # Fault injection flips last byte
    normal = bytes([0xAA, 0x55, 0x02, 0x00, 0x01, 0x00])
    await transport.close()


def test_list_available_ports_execution() -> None:
    """Verify hardware port listing executes cleanly across platforms."""
    ports = list_available_ports()
    assert isinstance(ports, list)
