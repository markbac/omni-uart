"""Linux/macOS integration tests for the PTY-backed transport (#195)."""

import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(os.name == "nt", reason="PTYs are POSIX only")

from omniuart.core.catalog import CatalogManager  # noqa: E402
from omniuart.core.session import DeviceSession  # noqa: E402
from omniuart.core.simulator import BaseDeviceSimulator  # noqa: E402
from omniuart.core.transport import HardwareSerialTransport, PtySerialPair, PtyTransport  # noqa: E402


@pytest.fixture()
async def pair():
    p = PtySerialPair()
    await p.open()
    yield p
    await p.close()


@pytest.mark.asyncio
async def test_bytes_cross_the_pty_in_both_directions(pair):
    assert pair.host.is_open and pair.device.is_open
    await pair.host.write(b"\x00\xaa\x55\r\n\xff")  # raw: no echo, no CR/LF translation
    assert await pair.device.read(size=6, timeout_ms=500) == b"\x00\xaa\x55\r\n\xff"
    await pair.device.write(b"reply")
    assert await pair.host.read(size=5, timeout_ms=500) == b"reply"


@pytest.mark.asyncio
async def test_partial_reads_keep_the_remainder(pair):
    await pair.host.write(b"abcdef")
    assert await pair.device.read(size=2, timeout_ms=500) == b"ab"
    assert await pair.device.read(size=10, timeout_ms=100) == b"cdef"  # timeout returns what arrived


@pytest.mark.asyncio
async def test_read_times_out_empty_and_polls_with_zero(pair):
    loop = asyncio.get_running_loop()
    started = loop.time()
    assert await pair.device.read(size=1, timeout_ms=80) == b""
    assert 0.06 <= loop.time() - started < 1.0
    started = loop.time()
    assert await pair.device.read(size=1, timeout_ms=0) == b""
    assert loop.time() - started < 0.05


@pytest.mark.asyncio
async def test_read_wakes_when_data_arrives_later(pair):
    reader = asyncio.create_task(pair.device.read(size=3, timeout_ms=2000))
    await asyncio.sleep(0.05)
    await pair.host.write(b"xyz")
    assert await asyncio.wait_for(reader, 1.0) == b"xyz"


@pytest.mark.asyncio
async def test_large_transfer_exceeding_the_kernel_buffer(pair):
    payload = bytes(range(256)) * 1024  # 256 KiB
    received = bytearray()

    async def drain():
        while len(received) < len(payload):
            chunk = await pair.device.read(size=4096, timeout_ms=2000)
            assert chunk, "stalled"
            received.extend(chunk)

    drainer = asyncio.create_task(drain())
    await pair.host.write(payload)
    await asyncio.wait_for(drainer, 10.0)
    assert bytes(received) == payload


@pytest.mark.asyncio
async def test_closed_transport_raises_and_close_is_idempotent():
    p = PtySerialPair()
    await p.open()
    await p.host.close()
    assert not p.host.is_open
    with pytest.raises(RuntimeError):
        await p.host.write(b"x")
    with pytest.raises(RuntimeError):
        await p.host.read(1, 10)
    await p.host.close()
    await p.close()
    await p.close()


@pytest.mark.asyncio
async def test_peer_close_is_reported_not_hung():
    p = PtySerialPair()
    await p.open()
    await p.device.write(b"last")
    await p.device.close()
    os.close(p.slave_fd)  # last handle on the slave side goes away
    assert await p.host.read(size=4, timeout_ms=500) == b"last"
    loop = asyncio.get_running_loop()
    started = loop.time()
    assert await p.host.read(size=1, timeout_ms=2000) == b""  # returns at once, not after 2 s
    assert loop.time() - started < 0.5 and p.host.peer_closed
    with pytest.raises(ConnectionError):
        await p.host.write(b"x")
    p.slave_fd = -1
    await p.close()


@pytest.fixture()
async def host_only():
    """A pty whose slave side is left for a separate program (or transport) to open by path."""
    p = PtySerialPair()
    await p.host.open()
    yield p
    await p.close()


@pytest.mark.asyncio
async def test_open_by_path_interoperates_with_pyserial(host_only):
    """The slave device node is a real tty: pyserial can open it and talk to the master side."""
    serial_side = HardwareSerialTransport(host_only.slave_pts_path, baudrate=115200)
    await serial_side.open()
    try:
        await host_only.host.write(b"ping")
        assert await serial_side.read(size=4, timeout_ms=500) == b"ping"
        await serial_side.write(b"pong")
        assert await host_only.host.read(size=4, timeout_ms=500) == b"pong"
    finally:
        await serial_side.close()


@pytest.mark.asyncio
async def test_pty_transport_by_path_and_argument_validation(host_only):
    by_path = PtyTransport(path=host_only.slave_pts_path)
    await by_path.open()
    await host_only.host.write(b"hi")
    assert await by_path.read(size=2, timeout_ms=500) == b"hi"
    await by_path.close()
    with pytest.raises(ValueError):
        PtyTransport()
    with pytest.raises(ValueError):
        PtyTransport(fd=1, path="/dev/null")


@pytest.mark.asyncio
async def test_device_session_and_simulator_over_a_pty(pair):
    spec = CatalogManager().get_protocol("binary_sensor_node")
    sim = BaseDeviceSimulator(spec=spec, transport=pair.device, latency_ms=0)
    await sim.start()
    try:
        async with DeviceSession(spec, pair.host) as session:
            exchange = await session.send("get_readings", {"channel": 1}, timeout_ms=1000)
        assert exchange.ok and exchange.response.name == "get_readings"
    finally:
        await sim.stop()
