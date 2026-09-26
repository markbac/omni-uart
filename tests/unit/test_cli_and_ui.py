"""Unit tests for CLI commands and FastAPI Dynamic Web UI endpoints."""

from fastapi.testclient import TestClient
import pytest

from omniuart.cli import format_protocol_help, main as cli_main
from omniuart.core.catalog import CatalogManager
from omniuart.ui.app import app

client = TestClient(app)


def test_cli_list_command(capsys) -> None:
    """Verify CLI list command outputs discovered protocols and scripts."""
    exit_code = cli_main(["list"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Discovered Protocols" in captured.out
    assert "Discovered Scripts" in captured.out


def test_cli_info_command(capsys) -> None:
    """Verify CLI info command outputs rich protocol documentation with tag tabs."""
    exit_code = cli_main(["info", "binary_sensor_node"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "PROTOCOL HELP: BinarySensorNode" in captured.out
    assert "COMMAND CATALOG & PARAMETERS" in captured.out


def test_cli_send_command(capsys) -> None:
    """Verify CLI send command executes dry-run simulation."""
    exit_code = cli_main(["send", "binary_sensor_node", "get_readings", "-p", "channel=1"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Executing command 'get_readings'" in captured.out
    assert "[DRY-RUN SIMULATION OK]" in captured.out


def test_ui_api_protocols_list() -> None:
    """Verify GET /api/protocols endpoint returns catalog summary."""
    response = client.get("/api/protocols")
    assert response.status_code == 200
    data = response.json()
    assert data["protocols_found"] >= 4


def test_ui_api_protocol_spec_and_tags() -> None:
    """Verify GET /api/protocol/{identifier} returns spec and tag breakdown."""
    response = client.get("/api/protocol/binary_sensor_node.yaml")
    assert response.status_code == 200
    data = response.json()
    assert "spec" in data
    assert "tags" in data
    assert "dashboard" in data["tags"]


def test_ui_api_dashboard_auto_run() -> None:
    """Verify GET /api/dashboard/auto-run/{identifier} auto-executes dashboard-tagged commands."""
    response = client.get("/api/dashboard/auto-run/binary_sensor_node.yaml")
    assert response.status_code == 200
    data = response.json()
    assert data["dashboard_commands_executed"] >= 1
    assert "data" in data
