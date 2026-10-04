import pytest
import asyncio
from omniuart.core.catalog import CatalogManager
from omniuart.core.session import SerialSession, SessionState, ExchangeStatus, CommandBlockedError
from omniuart.core.transport import AsyncTransport

class TimingOutTransport(AsyncTransport):
    def __init__(self):
        self._open = False
    async def open(self):
        self._open = True
    async def close(self):
        self._open = False
    @property
    def is_open(self):
        return self._open
    async def write(self, data: bytes) -> int:
        return len(data)
    async def read(self, size: int = 1, timeout_ms: int = 1000) -> bytes:
        return b""
    async def set_pin_state(self, pin: str, state: bool) -> None:
        pass

@pytest.fixture
def dummy_spec():
    catalog = CatalogManager()
    return catalog.get_protocol("binary_sensor_node.yaml")

@pytest.mark.asyncio
async def test_serial_session_lifecycle(dummy_spec):
    transport = TimingOutTransport()
    session = SerialSession(dummy_spec, transport)

    assert session.state == SessionState.CLOSED
    assert not session.is_open

    async with session:
        assert session.state == SessionState.OPEN
        assert session.is_open

    assert session.state == SessionState.CLOSED
    assert not session.is_open

@pytest.mark.asyncio
async def test_serial_session_statistics(dummy_spec):
    from omniuart.core.transport import VirtualTransport
    transport = VirtualTransport(dummy_spec)
    session = SerialSession(dummy_spec, transport)

    await session.open()
    stats = session.get_statistics()
    assert stats.total_requests == 0

    exchange = await session.send("ping")
    assert exchange.ok

    stats = session.get_statistics()
    assert stats.total_requests == 1
    assert stats.successful_requests == 1
    assert stats.bytes_sent > 0
    assert stats.average_latency_ms >= 0

    session.reset_statistics()
    assert session.get_statistics().total_requests == 0
    await session.close()

@pytest.mark.asyncio
async def test_serial_session_read_only_mode(dummy_spec):
    from omniuart.core.transport import VirtualTransport
    transport = VirtualTransport(dummy_spec)
    session = SerialSession(dummy_spec, transport, read_only=True)

    await session.open()
    # ping is read_only so it succeeds
    ex1 = await session.send("ping")
    assert ex1.ok

    # set_sampling_rate is not read_only so it raises CommandBlockedError
    with pytest.raises(CommandBlockedError):
        await session.send("set_sampling_rate", {"rate_hz": 10})

    await session.close()

@pytest.mark.asyncio
async def test_serial_session_retry_on_timeout(dummy_spec):
    transport = TimingOutTransport()
    session = SerialSession(dummy_spec, transport)

    await session.open()
    ex = await session.send("ping", timeout_ms=10, retries=2)
    assert ex.status == ExchangeStatus.TIMEOUT
    # Should have tried 3 times (initial + 2 retries)
    assert session.get_statistics().total_requests == 3
    assert session.get_statistics().failed_requests == 3
    await session.close()
