"""Unit tests for Application Services Layer (#208, #314, #315)."""

import pytest
from pathlib import Path
from omniuart.services import (
    CatalogService,
    CommandExecutionService,
    AutomationService,
    DocumentationService,
    FuzzingService,
    GeneratorService,
)

def test_catalog_service():
    service = CatalogService()
    summary = service.list_catalog()
    assert "protocols" in summary
    assert "scripts" in summary
    assert len(summary["protocols"]) > 0
    assert len(summary["scripts"]) > 0
    assert any(s["name"] for s in summary["scripts"])

    p = service.get_protocol("binary_sensor_node.yaml")
    assert p.metadata.name is not None

@pytest.mark.asyncio
async def test_command_execution_service_dry_run():
    service = CatalogService()
    spec = service.get_protocol("binary_sensor_node.yaml")

    cmd_service = CommandExecutionService()
    res = await cmd_service.execute_command(spec, "ping", {}, dry_run=True)
    assert res["dry_run"] is True
    assert res["command"] == "ping"
    assert "request_hex" in res

@pytest.mark.asyncio
async def test_automation_service():
    auto_service = AutomationService()
    res = await auto_service.run_script("sensor_test_suite.yaml", virtual=True)
    assert "script" in res
    assert "total_steps" in res
    assert res["total_steps"] > 0

def test_documentation_service(tmp_path: Path):
    doc_service = DocumentationService()
    out = doc_service.generate_documentation(protocol="binary_sensor_node.yaml", output_dir=str(tmp_path))
    assert out.exists()
    assert "<!DOCTYPE html>" in out.read_text(encoding="utf-8")

@pytest.mark.asyncio
async def test_fuzzing_service():
    fuzz_service = FuzzingService()
    res = await fuzz_service.run_fuzz_campaign("binary_sensor_node.yaml", num_vectors=5, seed=42)
    assert res["protocol"] == "BinarySensorNode"
    assert res["vectors"] == 5
    assert "passed" in res

@pytest.mark.asyncio
async def test_generator_service():
    service = GeneratorService()
    code = service.generate("python", "binary_sensor_node.yaml")
    assert "dataclass" in code

    schema = service.generate("schema")
    assert "schema" in schema.lower()
