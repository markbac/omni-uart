"""Windows-only integration tests for the real named-pipe transport (#194)."""

import asyncio
import os
import sys
import textwrap
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows named pipes")

from omniuart.core.catalog import CatalogManager  # noqa: E402
from omniuart.core.session import DeviceSession  # noqa: E402
from omniuart.core.simulator import BaseDeviceSimulator  # noqa: E402
from omniuart.core.transport import WindowsNamedPipePair, WindowsNamedPipeTransport  # noqa: E402


@pytest.fixture()
async def pair():
    p = WindowsNamedPipePair()
    await p.open()
    yield p
    await p.close()


@pytest.mark.asyncio
async def test_pipe_name_is_a_real_windows_pipe_path():
    t = WindowsNamedPipeTransport("abc")
    assert t.pipe_name == "\\\\.\\pipe\\abc"
    assert WindowsNamedPipeTransport("\\\\.\\pipe\\xyz").pipe_name == "\\\\.\\pipe\\xyz"


@pytest.mark.asyncio
async def test_bytes_cross_the_pipe_in_both_directions(pair):
    assert pair.host.connected and pair.device.connected
    await pair.host.write(b"\x00\xaa\x55\r\n\xff")
    assert await pair.device.read(size=6, timeout_ms=1000) == b"\x00\xaa\x55\r\n\xff"
    await pair.device.write(b"reply")
    assert await pair.host.read(size=5, timeout_ms=1000) == b"reply"


@pytest.mark.asyncio
async def test_partial_reads_keep_the_remainder_and_timeouts_return_what_arrived(pair):
    await pair.host.write(b"abcdef")
    assert await pair.device.read(size=2, timeout_ms=1000) == b"ab"
    assert await pair.device.read(size=10, timeout_ms=150) == b"cdef"
    loop = asyncio.get_running_loop()
    started = loop.time()
    assert await pair.device.read(size=1, timeout_ms=100) == b""
    assert loop.time() - started >= 0.08
    assert await pair.device.read(size=1, timeout_ms=0) == b""


@pytest.mark.asyncio
async def test_read_wakes_when_data_arrives_later(pair):
    reader = asyncio.create_task(pair.device.read(size=3, timeout_ms=3000))
    await asyncio.sleep(0.05)
    await pair.host.write(b"xyz")
    assert await asyncio.wait_for(reader, 2.0) == b"xyz"


@pytest.mark.asyncio
async def test_larger_transfer_in_chunks(pair):
    payload = bytes(range(256)) * 256  # 64 KiB
    received = bytearray()

    async def drain():
        while len(received) < len(payload):
            chunk = await pair.device.read(size=4096, timeout_ms=3000)
            assert chunk, "stalled"
            received.extend(chunk)

    drainer = asyncio.create_task(drain())
    for i in range(0, len(payload), 4096):
        await pair.host.write(payload[i : i + 4096])
    await asyncio.wait_for(drainer, 10.0)
    assert bytes(received) == payload


@pytest.mark.asyncio
async def test_closed_transport_raises_and_close_is_idempotent():
    p = WindowsNamedPipePair()
    await p.open()
    await p.device.close()
    with pytest.raises(RuntimeError):
        await p.device.write(b"x")
    with pytest.raises(RuntimeError):
        await p.device.read(1, 10)
    await p.device.close()
    await p.close()
    await p.close()


@pytest.mark.asyncio
async def test_peer_disconnect_is_reported_not_hung():
    p = WindowsNamedPipePair()
    await p.open()
    await p.device.write(b"last")
    await p.device.close()
    assert await p.host.read(size=4, timeout_ms=2000) == b"last"
    loop = asyncio.get_running_loop()
    started = loop.time()
    assert await p.host.read(size=1, timeout_ms=3000) == b""
    assert loop.time() - started < 1.5 and p.host.peer_closed
    with pytest.raises(ConnectionError):
        await p.host.write(b"x")
    await p.close()


@pytest.mark.asyncio
async def test_client_without_a_server_fails_after_its_connect_timeout():
    client = WindowsNamedPipeTransport(f"omniuart_missing_{uuid.uuid4().hex[:8]}", role="client", connect_timeout_s=0.3)
    with pytest.raises(ConnectionError):
        await client.open()
    assert not client.is_open


@pytest.mark.asyncio
async def test_write_before_a_client_connects_is_an_error():
    server = WindowsNamedPipeTransport(f"omniuart_lonely_{uuid.uuid4().hex[:8]}", role="server")
    await server.open()
    try:
        assert not await server.wait_connected(0.1)
        with pytest.raises(ConnectionError):
            await server.write(b"x")
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_a_separate_process_can_talk_over_the_pipe():
    """A real second process connects to the pipe, proving this is an OS pipe and not an in-memory queue."""
    name = f"omniuart_xproc_{uuid.uuid4().hex[:8]}"
    server = WindowsNamedPipeTransport(name, role="server")
    await server.open()
    child_code = textwrap.dedent(
        f"""
        import asyncio
        from omniuart.core.transport import WindowsNamedPipeTransport

        async def main():
            t = WindowsNamedPipeTransport({name!r}, role="client")
            await t.open()
            data = await t.read(size=5, timeout_ms=5000)
            await t.write(data[::-1])
            await asyncio.sleep(0.2)
            await t.close()

        asyncio.run(main())
        """
    )
    child = await asyncio.create_subprocess_exec(sys.executable, "-c", child_code, stderr=asyncio.subprocess.PIPE)
    try:
        assert await server.wait_connected(10.0)
        await server.write(b"hello")
        assert await server.read(size=5, timeout_ms=10000) == b"olleh"
        _, err = await asyncio.wait_for(child.communicate(), 10.0)
        assert child.returncode == 0, err.decode()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_device_session_and_simulator_over_a_named_pipe(pair):
    spec = CatalogManager().get_protocol("binary_sensor_node")
    sim = BaseDeviceSimulator(spec=spec, transport=pair.device, latency_ms=0)
    await sim.start()
    try:
        async with DeviceSession(spec, pair.host) as session:
            exchange = await session.send("get_readings", {"channel": 1}, timeout_ms=2000)
        assert exchange.ok and exchange.response.name == "get_readings"
    finally:
        await sim.stop()
