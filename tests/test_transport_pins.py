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


@pytest.mark.asyncio
async def test_windows_named_pipe_transport() -> None:
    from omniuart.core.transport import WindowsNamedPipeTransport
    pipe = WindowsNamedPipeTransport("test_vcom")
    await pipe.open()
    assert pipe.is_open is True

    await pipe.write(b"HELLO PIPE\r\n")
    read_back = await pipe.read(size=12, timeout_ms=500)
    assert read_back == b"HELLO PIPE\r\n"

    await pipe.close()
    assert pipe.is_open is False


@pytest.mark.asyncio
async def test_pty_serial_pair_raises_on_windows_or_works_posix() -> None:
    import os
    from omniuart.core.transport import PtySerialPair

    if os.name == "nt":
        with pytest.raises(NotImplementedError):
            PtySerialPair()
    else:
        pty_pair = PtySerialPair()
        await pty_pair.open()
        assert pty_pair.slave_pts_path.startswith("/dev/pts")
        await pty_pair.close()

