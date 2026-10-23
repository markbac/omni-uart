"""Unit tests for the Application Services Layer used by the CLI and web API (#208, #314, #315)."""

from pathlib import Path

import pytest

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import CommandSafety, CommandSpec
from omniuart.core.session import ExchangeStatus
from omniuart.services import (
    AutomationService,
    CatalogService,
    CommandExecutionService,
    DocumentationService,
    ErrorKind,
    FuzzingService,
    GeneratorService,
    ReplayService,
    ServiceError,
    check_command_allowed,
)


def test_catalog_service_lookups():
    service = CatalogService()
    summary = service.summary()
    assert summary["protocols"] and summary["scripts"]

    spec = service.get_protocol("binary_sensor_node.yaml")
    assert service.get_command(spec, "ping").name == "ping"
    with pytest.raises(ServiceError) as exc:
        service.get_protocol("no_such_protocol_xyz")
    assert exc.value.kind is ErrorKind.NOT_FOUND
    with pytest.raises(ServiceError) as exc:
        service.get_command(spec, "no_such_command")
    assert exc.value.kind is ErrorKind.NOT_FOUND


def test_catalog_service_reports_files_that_fail_to_load(tmp_path: Path):
    (tmp_path / "broken.yaml").write_text("metadata: [not, a, mapping]\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    service = CatalogService(CatalogManager(protocol_dirs=[tmp_path], script_dirs=[tmp_path / "scripts"]))
    assert [e["filename"] for e in service.summary()["errors"]] == ["broken.yaml"]
    with pytest.raises(ServiceError) as exc:
        service.get_protocol("broken")
    assert exc.value.kind is ErrorKind.INVALID


def test_check_command_allowed_rules():
    write = CommandSpec(name="write", id=1, safety=CommandSafety.MUTATING)
    read = CommandSpec(name="read", id=2, safety=CommandSafety.READ_ONLY)
    check_command_allowed(read, read_only=True, confirmed=False)
    with pytest.raises(ServiceError) as exc:
        check_command_allowed(write, read_only=True, confirmed=True)
    assert exc.value.kind is ErrorKind.BLOCKED
    with pytest.raises(ServiceError) as exc:
        check_command_allowed(write, read_only=False, confirmed=False)
    assert exc.value.kind is ErrorKind.CONFIRMATION_REQUIRED
    check_command_allowed(write, read_only=False, confirmed=False, confirm_levels={CommandSafety.DESTRUCTIVE})


def test_command_execution_dry_run_and_virtual_send(tmp_path: Path):
    service = CommandExecutionService()
    spec = CatalogService().get_protocol("binary_sensor_node.yaml")

    dry = service.execute(spec, "ping", {}, dry_run=True)
    assert dry.exchange is None and dry.request

    record = tmp_path / "send.jsonl"
    sent = service.execute(spec, "ping", {}, virtual=True, record_file=str(record))
    assert sent.exchange is not None and sent.exchange.status is ExchangeStatus.OK
    assert record.is_file()

    with pytest.raises(ServiceError) as exc:
        service.execute(spec, "ping", {}, port=None, virtual=False)
    assert exc.value.kind is ErrorKind.INVALID
    with pytest.raises(ServiceError) as exc:
        service.execute(spec, "get_readings", {"channel": 999}, dry_run=True)
    assert exc.value.kind is ErrorKind.INVALID


def test_automation_and_replay_services(tmp_path: Path):
    record = tmp_path / "session.jsonl"
    outcome = AutomationService().run("sensor_test_suite.yaml", virtual=True, record_file=str(record))
    assert outcome.result.steps and outcome.result.exit_code == 0
    assert record.is_file()

    replayed = ReplayService().replay(str(record), virtual=True, speed=100.0)
    assert replayed.frames_sent > 0 and replayed.truncated is False
    with pytest.raises(ServiceError) as exc:
        ReplayService().replay(str(tmp_path / "missing.jsonl"), virtual=True)
    assert exc.value.kind is ErrorKind.NOT_FOUND


def test_automation_service_refuses_paths_when_asked():
    with pytest.raises(ServiceError) as exc:
        AutomationService().prepare("examples/scripts/sensor_test_suite.yaml", allow_path=False)
    assert exc.value.kind is ErrorKind.NOT_FOUND


def test_documentation_service(tmp_path: Path):
    service = DocumentationService()
    single = service.generate(protocol="binary_sensor_node.yaml", output_dir=str(tmp_path / "one"))
    assert "<!DOCTYPE html>" in single.written[0].read_text(encoding="utf-8")

    every = service.generate(all_protocols=True, fmt="markdown", output_dir=str(tmp_path / "all"))
    assert not every.failures
    assert len(every.written) == len(CatalogManager().list_protocol_files())


def test_fuzzing_service():
    outcome = FuzzingService().run("binary_sensor_node.yaml", vectors=5, seed=42, virtual=True)
    report = outcome.report
    assert outcome.target == "virtual simulator"
    assert report.total_vectors == sum(report.outcomes.values()) > 0
    with pytest.raises(ServiceError) as exc:
        FuzzingService().run("no_such_protocol_xyz")
    assert exc.value.kind is ErrorKind.INVALID


def test_generator_service():
    service = GeneratorService()
    assert "dataclass" in service.generate("python", "binary_sensor_node.yaml")
    assert "schema" in service.generate("schema").lower()
    assert '"asyncapi"' in service.generate("asyncapi", "binary_sensor_node.yaml")
    with pytest.raises(ServiceError):
        service.generate("python")
