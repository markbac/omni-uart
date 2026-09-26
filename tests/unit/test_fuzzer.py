"""Unit tests for ProtocolFuzzer and CLI fuzz subcommand."""

import asyncio
from pathlib import Path
import pytest

from omniuart.cli import main as cli_main
from omniuart.core.catalog import CatalogManager
from omniuart.core.fuzzer import ProtocolFuzzer
from omniuart.core.transport import VirtualTransport

PROTO_FILE = Path("examples/protocols/binary_sensor_node.yaml")


@pytest.mark.asyncio
async def test_protocol_fuzzer_campaign() -> None:
    """Verify generating fuzz vectors and executing campaign against VirtualTransport."""
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node")
    assert spec is not None

    fuzzer = ProtocolFuzzer(spec)
    transport = VirtualTransport(spec, latency_ms=1.0)

    report = await fuzzer.run_campaign(transport, max_vectors=10)
    assert report.protocol_name == spec.metadata.name
    assert report.total_vectors > 0
    assert report.handled_count >= 1


def test_cli_fuzz_command(capsys) -> None:
    """Verify CLI fuzz subcommand execution."""
    exit_code = cli_main(["fuzz", "binary_sensor_node", "-n", "5"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Starting Fuzzing Campaign for 'BinarySensorNode'" in captured.out
    assert "Campaign Completed" in captured.out
