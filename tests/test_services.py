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
    ReplayService,
)
from omniuart.core.catalog import CatalogManager

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
    assert res["vectors"] == sum(res["outcomes"].values()) > 0
    assert res["handled"] + res["failed"] == res["vectors"]
    assert res["passed"] is (res["failed"] == 0)

@pytest.mark.asyncio
async def test_generator_service():
    service = GeneratorService()
    code = service.generate("python", "binary_sensor_node.yaml")
    assert "dataclass" in code

    schema = service.generate("schema")
    assert "schema" in schema.lower()


def test_catalog_service_reports_files_that_fail_to_load(tmp_path: Path):
    (tmp_path / "broken.yaml").write_text("metadata: [not, a, mapping]\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    service = CatalogService(CatalogManager(protocol_dirs=[tmp_path], script_dirs=[tmp_path / "scripts"]))
    summary = service.list_catalog()
    assert summary["protocols"] == []
    assert [e["filename"] for e in summary["errors"]] == ["broken.yaml"]


def test_documentation_service_all_protocols(tmp_path: Path):
    out = DocumentationService().generate_documentation(all_protocols=True, output_dir=str(tmp_path))
    assert any(out.glob("*.html"))


@pytest.mark.asyncio
async def test_automation_and_replay_services(tmp_path: Path):
    record = tmp_path / "session.jsonl"
    res = await AutomationService().run_script("sensor_test_suite.yaml", virtual=True, record_file=str(record))
    assert res["passed"] + res["skipped"] + res["failed"] == res["total_steps"]
    assert record.is_file()

    replayed = await ReplayService().replay(str(record), virtual=True, speed=100.0)
    assert replayed["events_replayed"] > 0
    assert replayed["truncated"] is False
