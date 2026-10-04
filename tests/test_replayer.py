"""Tests for SessionReplayer module."""

from __future__ import annotations

from pathlib import Path
import pytest
from omniuart.cli import main as cli_main
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
    replayer = SessionReplayer(transport, speed_multiplier=0.0)

    count = await replayer.replay_file(jsonl_file)
    assert count == 2


@pytest.mark.asyncio
async def test_replayer_malformed_jsonl_line_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.jsonl"
    bad_file.write_text("{\"direction\": \"tx\", \"raw_hex\": \"AA55\", \"length_bytes\": 2}\nNOT_VALID_JSON\n", encoding="utf-8")

    transport = VirtualTransport()
    replayer = SessionReplayer(transport)

    with pytest.raises(ValueError) as exc_info:
        await replayer.replay_file(bad_file)
    assert "Line 2" in str(exc_info.value)


def test_cli_replay_command(tmp_path: Path) -> None:
    recorder = SessionRecorder()
    recorder.record("tx", b"\xAA\x55\x01", command_name="ping")
    jsonl_file = tmp_path / "cli_replay.jsonl"
    recorder.export_jsonl(jsonl_file)

    code = cli_main(["replay", str(jsonl_file), "--speed", "0", "--virtual"])
    assert code == 0
