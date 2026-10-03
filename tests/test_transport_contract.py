"""Read/timeout contract shared by every transport (#196, #265, #266)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Awaitable, Callable, Tuple

import pytest

from omniuart.core.transport import (
    AsyncTransport,
    HardwareSerialTransport,
    PtySerialPair,
    VirtualSerialPair,
    VirtualTransport,
)

Inject = Callable[[bytes], Awaitable[None]]


async def _virtual() -> Tuple[AsyncTransport, Inject, Callable[[], Awaitable[None]]]:
    t = VirtualTransport(None, latency_ms=0, jitter_ms=0)
    await t.open()

    async def inject(data: bytes) -> None:
        t._rx.feed(data)

    return t, inject, t.close


async def _pipe() -> Tuple[AsyncTransport, Inject, Callable[[], Awaitable[None]]]:
    pair = VirtualSerialPair()
    await pair.open()
    return pair.host, pair.device.write, pair.close  # type: ignore[return-value]


async def _loopback() -> Tuple[AsyncTransport, Inject, Callable[[], Awaitable[None]]]:
    t = HardwareSerialTransport("loop://", 115200)
    await t.open()

    async def inject(data: bytes) -> None:
        await t.write(data)

    return t, inject, t.close


async def _pty() -> Tuple[AsyncTransport, Inject, Callable[[], Awaitable[None]]]:
    pair = PtySerialPair()
    await pair.open()
    return pair.host, pair.device.write, pair.close  # type: ignore[return-value]


FACTORIES = {"virtual": _virtual, "pipe": _pipe, "serial-loop": _loopback}
if os.name != "nt":
    FACTORIES["pty"] = _pty


@pytest.fixture(params=list(FACTORIES))
async def endpoint(request):
    transport, inject, close = await FACTORIES[request.param]()
    yield transport, inject
    await close()


@pytest.mark.asyncio
async def test_zero_timeout_polls_and_returns_immediately(endpoint) -> None:
    transport, _ = endpoint
    start = time.monotonic()
    assert await asyncio.wait_for(transport.read(1, timeout_ms=0), 1.0) == b""
    assert time.monotonic() - start < 0.5


@pytest.mark.asyncio
async def test_zero_timeout_returns_what_is_already_buffered(endpoint) -> None:
    transport, inject = endpoint
    await inject(b"xyz")
    await asyncio.sleep(0.15)
    assert await asyncio.wait_for(transport.read(10, timeout_ms=0), 1.0) == b"xyz"


@pytest.mark.asyncio
async def test_surplus_bytes_stay_buffered_for_the_next_read(endpoint) -> None:
    transport, inject = endpoint
    await inject(b"\xaa\x01\x02\x03\x04\x05\x06\x07")
    assert await transport.read(1, timeout_ms=500) == b"\xaa"
    assert await transport.read(7, timeout_ms=500) == b"\x01\x02\x03\x04\x05\x06\x07"


@pytest.mark.asyncio
async def test_timeout_returns_the_partial_data_that_arrived(endpoint) -> None:
    transport, inject = endpoint
    await inject(b"abc")
    start = time.monotonic()
    assert await transport.read(10, timeout_ms=200) == b"abc"
    assert 0.15 <= time.monotonic() - start < 1.0


@pytest.mark.asyncio
async def test_timeout_is_an_absolute_deadline_not_per_chunk(endpoint) -> None:
    transport, inject = endpoint

    async def trickle() -> None:
        for _ in range(8):
            await asyncio.sleep(0.05)
            await inject(b"x")

    task = asyncio.create_task(trickle())
    start = time.monotonic()
    data = await transport.read(100, timeout_ms=200)
    elapsed = time.monotonic() - start
    await task
    assert elapsed < 0.6, "each arriving chunk must not restart the timeout"
    assert 1 <= len(data) < 8


@pytest.mark.asyncio
async def test_none_waits_until_the_data_arrives(endpoint) -> None:
    transport, inject = endpoint

    async def later() -> None:
        await asyncio.sleep(0.2)
        await inject(b"ok")

    task = asyncio.create_task(later())
    assert await asyncio.wait_for(transport.read(2, timeout_ms=None), 3.0) == b"ok"
    await task


@pytest.mark.asyncio
async def test_cancelled_read_does_not_lose_later_data(endpoint) -> None:
    transport, inject = endpoint
    reader = asyncio.create_task(transport.read(1, timeout_ms=None))
    await asyncio.sleep(0.1)
    reader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reader
    await inject(b"k")
    assert await transport.read(1, timeout_ms=500) == b"k"


@pytest.mark.asyncio
async def test_unknown_pin_is_rejected_the_same_way_everywhere(endpoint) -> None:
    transport, _ = endpoint
    with pytest.raises(ValueError):
        await transport.set_pin_state("cts", True)
    await transport.set_pin_state("DTR", True)  # known pins are accepted case-insensitively
