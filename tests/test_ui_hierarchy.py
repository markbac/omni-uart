"""Unit test suite for Web UI hierarchical tag tree, serial ports, plotter, and script runner endpoints."""

from fastapi.testclient import TestClient
from omniuart.ui.app import app

client = TestClient(app)


def test_ui_protocols_list():
    response = client.get("/api/protocols")
    assert response.status_code == 200
    data = response.json()
    assert "protocols" in data
    assert len(data["protocols"]) > 0


def test_ui_protocol_tag_hierarchy():
    response = client.get("/api/protocol/ubx-uart-interface.json")
    assert response.status_code == 200
    data = response.json()
    assert "spec" in data
    assert "tags" in data
    assert "tag_groups" in data
    assert "gnss/nav" in data["tags"] or "gnss/config" in data["tags"]


def test_ui_serial_ports_and_connect():
    resp = client.get("/api/serial/ports")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["ports"], list)  # real ports only; may be empty
    assert data["virtual_port"] == "virtual"

    conn_resp = client.post("/api/serial/connect", json={"port": "virtual", "baudrate": 115200, "protocol": "binary_sensor_node"})
    assert conn_resp.status_code == 200
    assert conn_resp.json()["connection"]["simulated"] is True
    assert client.post("/api/serial/disconnect").json()["connection"]["connected"] is False


def test_ui_scripts_list_and_run():
    resp = client.get("/api/scripts")
    assert resp.status_code == 200
    data = resp.json()
    assert "scripts" in data

    client.post("/api/serial/connect", json={"port": "virtual", "protocol": "binary_sensor_node"})
    try:
        run_resp = client.post("/api/script/run/sensor_test_suite")
    finally:
        client.post("/api/serial/disconnect")
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["status"] == "PASSED" and body["simulated"] is True


def test_ui_index_html_renders_workspace_tabs_and_plotter():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "workspace-nav" in html
    assert "telemetryCanvas" in html
    assert "tagTreeMenu" in html
    assert "renderTagTree" in html
    assert "getDiscriminatorBadge" in html
    assert "badge-disc" in html
