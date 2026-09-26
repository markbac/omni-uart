"""Unit tests for DTR/RTS hardware line toggling and pin pulsing."""

from __future__ import annotations

import pytest
from omniuart.core.transport import VirtualTransport


@pytest.mark.asyncio
async def test_virtual_transport_pin_toggling() -> None:
    transport = VirtualTransport()
    await transport.open()
    
    assert transport.pin_states["dtr"] is False
    assert transport.pin_states["rts"] is False

    await transport.set_pin_state("dtr", True)
    assert transport.pin_states["dtr"] is True

    await transport.set_pin_state("rts", True)
    assert transport.pin_states["rts"] is True

    # Test pulse sequence
    sequence = [
        {"pin": "dtr", "state": False, "duration_ms": 10},
        {"pin": "rts", "state": False, "duration_ms": 10},
    ]
    await transport.pulse_pins(sequence)
    assert transport.pin_states["dtr"] is False
    assert transport.pin_states["rts"] is False

    await transport.close()
