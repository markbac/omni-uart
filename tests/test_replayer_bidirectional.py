import pytest
from pathlib import Path
from omniuart.core.recorder import SessionRecorder
from omniuart.core.replayer import SessionReplayer, ReplayDirectionMode, ReplayTimingMode
from omniuart.core.transport import VirtualTransport

@pytest.mark.asyncio
async def test_replayer_bidirectional_mode(tmp_path: Path):
    recorder = SessionRecorder()
    recorder.record("tx", b"\xAA\x55\x01", command_name="ping")
    recorder.record("rx", b"\xAA\x55\x81", command_name="ping_ack")
    recorder.record("tx", b"\xAA\x55\x02", command_name="pong")

    jsonl_path = tmp_path / "bidi_session.jsonl"
    recorder.export_jsonl(jsonl_path)

    transport = VirtualTransport()

    # TX only (default)
    replayer_tx = SessionReplayer(transport, timing_mode=ReplayTimingMode.DETERMINISTIC, direction_mode=ReplayDirectionMode.TX_ONLY)
    cnt_tx = await replayer_tx.replay_file(jsonl_path)
    assert cnt_tx == 2

    # RX emulate
    replayer_rx = SessionReplayer(transport, timing_mode=ReplayTimingMode.DETERMINISTIC, direction_mode=ReplayDirectionMode.RX_EMULATE)
    cnt_rx = await replayer_rx.replay_file(jsonl_path)
    assert cnt_rx == 1

    # Bidirectional
    replayer_bidi = SessionReplayer(transport, timing_mode=ReplayTimingMode.DETERMINISTIC, direction_mode=ReplayDirectionMode.BIDIRECTIONAL)
    cnt_bidi = await replayer_bidi.replay_file(jsonl_path)
    assert cnt_bidi == 3
