import pytest
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
async def test_generator_service():
    service = GeneratorService()
    code = service.generate("python", "binary_sensor_node.yaml")
    assert "dataclass" in code

    schema = service.generate("schema")
    assert "schema" in schema.lower()
