from pathlib import Path
import pytest
from omniuart.cli import main
from omniuart.core.transport import (
    VirtualSerialPair,
    list_available_ports,
)
from omniuart.hil import HILConfig, HILOrchestrator


# ---------------------------------------------------------------------------
# 1. Issue #342: Ports command & virtual serial pair enumeration
# ---------------------------------------------------------------------------
def test_virtual_serial_pair_registered_and_listed():
    # Before pair creation, check COM_VIRT_TEST is not in list
    ports_before = [p["device"] for p in list_available_ports()]
    assert "COM_HOST_TEST" not in ports_before

    pair = VirtualSerialPair(host_port="COM_HOST_TEST", device_port="COM_DEV_TEST")
    try:
        ports_after = [p["device"] for p in list_available_ports()]
        assert "COM_HOST_TEST" in ports_after
        assert "COM_DEV_TEST" in ports_after
    finally:
        import asyncio
        asyncio.run(pair.close())

    # After close, unregistered
    ports_closed = [p["device"] for p in list_available_ports()]
    assert "COM_HOST_TEST" not in ports_closed


def test_cli_ports_command(capsys):
    pair = VirtualSerialPair(host_port="COM_CLI_HOST", device_port="COM_CLI_DEV")
    try:
        assert main(["ports"]) == 0
        out = capsys.readouterr().out
        assert "COM_CLI_HOST" in out
        assert "COM_CLI_DEV" in out

        assert main(["ports", "--json"]) == 0
        out_json = capsys.readouterr().out
        assert "COM_CLI_HOST" in out_json
    finally:
        import asyncio
        asyncio.run(pair.close())


# ---------------------------------------------------------------------------
# 2. Issue #317: Tool entrypoints (dissect, visualize, benchmark, export, import)
# ---------------------------------------------------------------------------
def test_cli_dissect_command(capsys):
    from omniuart.core.catalog import CatalogManager
    from omniuart.core.codec import FrameCodec
    spec = CatalogManager().get_protocol("binary_sensor_node")
    raw = FrameCodec(spec).encode_command("ping")

    assert main(["dissect", "binary_sensor_node", raw.hex()]) == 0
    out = capsys.readouterr().out
    assert "FRAME DISSECTION" in out
    assert "VALID" in out


def test_cli_visualize_command(capsys, tmp_path):
    assert main(["visualize", "binary_sensor_node", "--format", "mermaid"]) == 0
    out = capsys.readouterr().out
    assert "sequenceDiagram" in out

    out_file = tmp_path / "viz.html"
    assert main(["visualize", "binary_sensor_node", "--format", "html", "--output", str(out_file)]) == 0
    assert out_file.exists()
    assert "<!DOCTYPE html>" in out_file.read_text(encoding="utf-8")


def test_cli_benchmark_command(capsys):
    assert main(["benchmark", "binary_sensor_node", "-n", "100"]) == 0
    out = capsys.readouterr().out
    assert "Benchmark Performance Suite Results" in out
    assert "codec_encode" in out


def test_cli_export_and_import_commands(capsys, tmp_path):
    csv_file = tmp_path / "exported.csv"
    assert main(["export", "binary_sensor_node", "--format", "csv", "-o", str(csv_file)]) == 0
    assert csv_file.exists()

    json_file = tmp_path / "imported.json"
    assert main(["import", str(csv_file), "-o", str(json_file)]) == 0
    assert json_file.exists()


# ---------------------------------------------------------------------------
# 3. Issue #324: HIL Orchestrator & CLI hil command
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hil_setup_teardown_and_error_summary(tmp_path: Path):
    artifacts_dir = tmp_path / "hil_artifacts"

    # Define setup sequence and teardown sequence
    config = HILConfig(
        virtual=True,
        pulse_reset=False,  # opt-in reset is disabled
        setup_sequence=[{"command": "ping"}],
        teardown_sequence=[{"command": "ping"}],
        artifacts_dir=str(artifacts_dir),
    )
    orchestrator = HILOrchestrator(config)
    result = await orchestrator.run_hil_test("sensor_test_suite.yaml")

    assert result.success is True
    assert result.exit_code == 0
    assert result.error_summary is None
    assert len(result.artifacts) == 2
    assert artifacts_dir.exists()


def test_cli_hil_command(capsys, tmp_path):
    artifacts_dir = tmp_path / "cli_hil_artifacts"
    assert main(["hil", "sensor_test_suite.yaml", "--virtual", "--artifacts", str(artifacts_dir)]) == 0
    out = capsys.readouterr().out
    assert "HIL Test Campaign: PASSED" in out


# ---------------------------------------------------------------------------
# 4. Issue #323: Fuzz CLI options (--port, --virtual, --read-only)
# ---------------------------------------------------------------------------
def test_cli_fuzz_options(capsys):
    assert main(["fuzz", "binary_sensor_node", "-n", "5", "--seed", "123", "--virtual", "--read-only"]) == 0
    out = capsys.readouterr().out
    assert "Starting Fuzzing Campaign" in out
    assert "virtual simulator" in out
    assert "Campaign Completed" in out
