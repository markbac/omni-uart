"""Tests for SessionReplayer module."""

from __future__ import annotations

from pathlib import Path
import pytest
from omniuart.core.recorder import SessionRecorder
from omniuart.core.replayer import SessionReplayer
from omniuart.core.transport import VirtualTransport


@pytest.mark.asyncio
async def test_session_replayer(tmp_path: Path) -> None:
    recorder = SessionRecorder()
    recorder.record("tx", b"\xAA\x55\x01\x00\x01\x00\x12\x34", command_name="ping")
    recorder.record("tx", b"\xAA\x55\x02\x00\x02\x00\x56\x78", command_name="get_readings")

    jsonl_file = tmp_path / "test_session.jsonl"
    recorder.export_jsonl(jsonl_file)

    transport = VirtualTransport()
    replayer = SessionReplayer(transport, speed_multiplier=10.0)

    count = await replayer.replay_file(jsonl_file)
    assert count == 2
