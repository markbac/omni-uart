"""The web API executes commands for real and never fabricates results (#253)."""

import pytest
from fastapi.testclient import TestClient

from omniuart.ui.app import app
from omniuart.ui.routes import connection, recorder


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
        c.post("/api/serial/disconnect")


def connect_virtual(client, protocol="binary_sensor_node"):
    return client.post("/api/serial/connect", json={"port": "virtual", "baudrate": 115200, "protocol": protocol})


def connect_loopback(client):
    """A real PySerial port whose far end just echoes: it never answers like a device."""
    return client.post("/api/serial/connect", json={"port": "loop://", "baudrate": 115200})


# ---------------------------------------------------------------- connect / disconnect
def test_connect_validates_baud_rate_and_port(client):
    assert client.post("/api/serial/connect", json={"port": "loop://", "baudrate": -5}).status_code == 422
    assert client.post("/api/serial/connect", json={"port": "loop://", "baudrate": 0}).status_code == 422
    assert client.post("/api/serial/connect", json={"port": "", "baudrate": 9600}).status_code == 422
    missing = client.post("/api/serial/connect", json={"port": "/dev/omniuart-no-such-port", "baudrate": 115200})
    assert missing.status_code == 400 and "Cannot open port" in missing.json()["detail"]
    assert client.get("/api/serial/status").json()["connection"]["connected"] is False


def test_connect_opens_a_real_transport_and_disconnect_closes_it(client):
    assert connect_loopback(client).status_code == 200
    transport = connection.transport
    assert transport is not None and transport.is_open
    assert client.get("/api/serial/status").json()["connection"]["port"] == "loop://"
    assert client.post("/api/serial/disconnect").status_code == 200
    assert not transport.is_open and not connection.connected
    assert client.post("/api/serial/disconnect").status_code == 200  # idempotent


def test_virtual_port_is_explicit_and_needs_a_protocol(client):
    assert client.post("/api/serial/connect", json={"port": "virtual"}).status_code == 422
    assert client.post("/api/serial/connect", json={"port": "virtual", "protocol": "nope"}).status_code == 422
    assert connect_virtual(client).json()["connection"]["simulated"] is True


def test_port_list_is_never_invented(client):
    ports = client.get("/api/serial/ports").json()["ports"]
    assert ports == [p["device"] for p in client.get("/api/ports").json()["ports"]]  # exactly what the OS reports


# ---------------------------------------------------------------- send
def test_send_requires_a_connection(client):
    resp = client.post("/api/send/binary_sensor_node", json={"command": "ping"})
    assert resp.status_code == 409


def test_send_unknown_protocol_and_command_are_404(client):
    connect_virtual(client)
    assert client.post("/api/send/no-such-protocol", json={"command": "ping"}).status_code == 404
    assert client.post("/api/send/binary_sensor_node", json={"command": "no-such"}).status_code == 404


def test_send_returns_the_real_frames_and_decoded_fields(client):
    connect_virtual(client)
    resp = client.post("/api/send/binary_sensor_node", json={"command": "get_readings", "params": {"channel": 2}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success" and body["simulated"] is True
    assert body["request_hex"].startswith("AA 55 01 00 02 02")  # built by the codec, not canned bytes
    assert body["response_hex"].startswith("AA 55")
    assert set(body["decoded_response"]) == {"channel", "temperature", "humidity", "pressure_hpa"}
    # The frames are recorded and visible to WebSocket clients
    assert [e.direction for e in recorder.events[-2:]] == ["tx", "rx"]


def test_send_differs_per_protocol_not_canned(client):
    connect_virtual(client, "binary_sensor_node")
    a = client.post("/api/send/binary_sensor_node", json={"command": "ping"}).json()
    assert "uptime_seconds" in a["decoded_response"] and "firmware_version" not in a["decoded_response"]


def test_send_rejects_invalid_parameters_with_422(client):
    connect_virtual(client)
    resp = client.post("/api/send/binary_sensor_node", json={"command": "get_readings", "params": {"channel": 99}})
    assert resp.status_code == 422 and "above the maximum" in resp.json()["detail"]


def test_a_device_that_does_not_answer_fails_the_request(client):
    assert connect_loopback(client).status_code == 200
    resp = client.post("/api/send/binary_sensor_node", json={"command": "ping"})
    assert resp.status_code in (502, 504)
    body = resp.json()
    assert body["status"] == "failed" and body["error"] and body["request_hex"].startswith("AA 55")


# ---------------------------------------------------------------- scripts
def test_unknown_script_is_404_and_needs_a_connection(client):
    assert client.post("/api/script/run/no-such-script").status_code == 404
    assert client.post("/api/script/run/sensor_test_suite").status_code == 409


def test_script_run_reports_real_results(client):
    connect_virtual(client)
    body = client.post("/api/script/run/sensor_test_suite").json()
    assert body["status"] == "PASSED" and body["total_steps"] == 5
    assert body["steps"][1]["fields"]["channel"] == 0 and body["steps"][1]["request"].startswith("aa 55")


def test_script_with_failing_assertions_reports_failed(client):
    connect_virtual(client, "smart_actuator")
    body = client.post("/api/script/run/actuator_calibration").json()
    assert body["status"] == "FAILED" and body["failed_steps"] >= 1
    assert any(step["status"] == "skipped" for step in body["steps"])


def test_script_against_a_dead_device_fails(client):
    assert connect_loopback(client).status_code == 200
    resp = client.post("/api/script/run/sensor_test_suite")
    assert resp.status_code == 200 and resp.json()["status"] == "FAILED"


# ---------------------------------------------------------------- dashboard
def test_dashboard_auto_run_needs_a_connection_and_unknown_protocol_is_404(client):
    assert client.get("/api/dashboard/auto-run/binary_sensor_node").status_code == 409
    assert client.get("/api/dashboard/auto-run/no-such").status_code == 404


def test_dashboard_auto_run_reports_each_command_for_real(client):
    connect_virtual(client)
    body = client.get("/api/dashboard/auto-run/binary_sensor_node").json()
    assert body["simulated"] is True and body["dashboard_commands_executed"] >= 1
    for result in body["data"].values():
        assert result["status"] in ("SUCCESS", "SKIPPED") and "firmware_version" not in (result.get("response") or {})


def test_dashboard_auto_run_against_a_dead_device_reports_failures(client):
    connect_loopback(client)
    body = client.get("/api/dashboard/auto-run/binary_sensor_node").json()
    assert body["data"] and all(r["status"] in ("FAILED", "SKIPPED") for r in body["data"].values())
    assert any(r["status"] == "FAILED" for r in body["data"].values())
