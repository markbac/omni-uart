import pytest
from pathlib import Path
from omniuart.hil import HILConfig, HILOrchestrator

@pytest.mark.asyncio
async def test_hil_orchestration(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    config = HILConfig(
        virtual=True,
        power_pin="dtr",
        reset_pin="rts",
        artifacts_dir=str(artifacts_dir)
    )

    orchestrator = HILOrchestrator(config)
    result = await orchestrator.run_hil_test("sensor_test_suite.yaml")

    assert result.total_steps > 0
    assert result.success is True
    assert result.exit_code == 0
    assert len(result.artifacts) == 2
    assert artifacts_dir.exists()
