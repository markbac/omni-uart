"""Unit tests for seedable, rich fault injection in VirtualTransport."""

from __future__ import annotations

import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.core.transport import VirtualTransport


@pytest.mark.asyncio
async def test_virtual_transport_seed_reproducibility() -> None:
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node.yaml")

    vt1 = VirtualTransport(protocol=spec, seed=42, bit_flip_rate=0.5, latency_ms=1.0)
    vt2 = VirtualTransport(protocol=spec, seed=42, bit_flip_rate=0.5, latency_ms=1.0)

    await vt1.open()
    await vt2.open()

    req = bytes([0xAA, 0x55, 0x01, 0x01, 0x00, 0x00, 0x00])

    await vt1.write(req)
    res1 = await vt1.read(32, timeout_ms=500)

    await vt2.write(req)
    res2 = await vt2.read(32, timeout_ms=500)

    assert res1 == res2


@pytest.mark.asyncio
async def test_virtual_transport_corrupt_crc() -> None:
    vt = VirtualTransport(seed=123, corrupt_crc_rate=1.0, latency_ms=1.0)
    await vt.open()

    req = bytes([0xAA, 0x55, 0x01, 0x00, 0x01, 0x00, 0x12, 0x34])
    await vt.write(req)
    res = await vt.read(32, timeout_ms=500)

    assert len(res) == len(req)
    assert res != req
    assert res[:-1] == req[:-1]
    assert res[-1] != req[-1]


@pytest.mark.asyncio
async def test_virtual_transport_truncation() -> None:
    vt = VirtualTransport(seed=999, truncate_rate=1.0, latency_ms=1.0)
    await vt.open()

    req = bytes([0xAA, 0x55, 0x01, 0x00, 0x01, 0x00, 0x12, 0x34])
    await vt.write(req)
    res = await vt.read(32, timeout_ms=500)

    assert 0 < len(res) < len(req)
