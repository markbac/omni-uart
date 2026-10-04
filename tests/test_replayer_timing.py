import pytest
from pathlib import Path
from omniuart.core.recorder import SessionRecorder
from omniuart.core.replayer import SessionReplayer, ReplayTimingMode
from omniuart.core.transport import VirtualTransport

@pytest.mark.asyncio
async def test_replayer_timing_modes(tmp_path: Path):
    recorder = SessionRecorder()
    recorder.record("tx", b"\xAA\x55\x01", command_name="ping")
    recorder.record("tx", b"\xAA\x55\x02", command_name="pong")

    jsonl_path = tmp_path / "timing_test.jsonl"
    recorder.export_jsonl(jsonl_path)

    transport = VirtualTransport()

    # Deterministic mode (zero delay)
    replayer_det = SessionReplayer(transport, timing_mode=ReplayTimingMode.DETERMINISTIC)
    cnt1 = await replayer_det.replay_file(jsonl_path)
    assert cnt1 == 2

    # Fixed rate mode
    replayer_fixed = SessionReplayer(transport, timing_mode=ReplayTimingMode.FIXED_RATE, fixed_interval_s=0.001)
    cnt2 = await replayer_fixed.replay_file(jsonl_path)
    assert cnt2 == 2

    # Faithful mode
    replayer_faithful = SessionReplayer(transport, timing_mode=ReplayTimingMode.FAITHFUL, max_gap_s=None)
    cnt3 = await replayer_faithful.replay_file(jsonl_path)
    assert cnt3 == 2
