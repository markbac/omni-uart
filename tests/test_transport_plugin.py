import pytest
from omniuart.core.transport import (
    AsyncTransport,
    TransportRegistry,
    transport_registry,
    register_transport,
    VirtualTransport,
)

class DummyCustomTransport(AsyncTransport):
    def __init__(self, tag: str = "default"):
        self.tag = tag
        self._is_open = False

    async def open(self) -> None:
        self._is_open = True

    async def close(self) -> None:
        self._is_open = False

    async def write(self, data: bytes) -> int:
        return len(data)

    async def read(self, size: int = 1, timeout_ms: int = 1000) -> bytes:
        return b""

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def set_pin_state(self, pin: str, state: bool) -> None:
        pass


def test_transport_registry():
    reg = TransportRegistry()
    reg.register("dummy", lambda **kw: DummyCustomTransport(**kw))

    assert "dummy" in reg.list_transports()

    t = reg.create("dummy", tag="custom_val")
    assert isinstance(t, DummyCustomTransport)
    assert t.tag == "custom_val"

    with pytest.raises(ValueError):
        reg.create("nonexistent")


def test_builtin_transport_plugins():
    assert "virtual" in transport_registry.list_transports()
    assert "serial" in transport_registry.list_transports()

    vt = transport_registry.create("virtual")
    assert isinstance(vt, VirtualTransport)
