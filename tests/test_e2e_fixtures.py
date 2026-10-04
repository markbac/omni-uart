"""End-to-end regression tests using curated protocol and session fixtures (#228)."""

from pathlib import Path
import pytest

from omniuart.core.codec import FrameCodec
from omniuart.core.models import load_protocol
from omniuart.core.replayer import SessionReplayer
from omniuart.core.transport import VirtualTransport

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_regression_protocol_fixture_loading():
    proto_file = FIXTURES_DIR / "regression_protocol.yaml"
    assert proto_file.exists()

    spec = load_protocol(proto_file)
    assert spec.metadata.name == "RegressionDevice"
    assert len(spec.commands) == 2

    codec = FrameCodec(spec)
    req = codec.encode_command("status")
    assert req.startswith(b"\xaa\x55")


@pytest.mark.asyncio
async def test_regression_session_replayer_fixture(tmp_path: Path):
    proto_file = FIXTURES_DIR / "regression_protocol.yaml"
    session_file = FIXTURES_DIR / "regression_session.jsonl"

    assert session_file.exists()

    spec = load_protocol(proto_file)
    transport = VirtualTransport(spec, latency_ms=0.0, jitter_ms=0.0)
    replayer = SessionReplayer(transport, direction_mode="bidirectional")

    count = await replayer.replay_file(session_file)
    assert count == 2
