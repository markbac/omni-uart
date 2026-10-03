"""Host/Origin guards for the local web UI (#268)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from omniuart.ui.app import app
from omniuart.ui.routes import active_connections
from omniuart.ui.security import is_loopback_host

client = TestClient(app)


def test_allowed_host_is_served() -> None:
    assert client.get("/api/protocols", headers={"Host": "localhost:8000"}).status_code == 200
    assert client.get("/api/protocols", headers={"Host": "127.0.0.1:9123"}).status_code == 200
    assert client.get("/api/protocols", headers={"Host": "[::1]:8000"}).status_code == 200


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "192.168.1.10:8000", "localhost.evil.example"])
def test_foreign_host_header_is_rejected(host: str) -> None:
    assert client.get("/api/protocols", headers={"Host": host}).status_code == 403


def test_cross_origin_post_is_rejected() -> None:
    r = client.post("/api/serial/disconnect", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_same_origin_post_and_originless_post_are_allowed() -> None:
    assert client.post("/api/serial/disconnect", headers={"Origin": "http://localhost:8000"}).status_code == 200
    assert client.post("/api/serial/disconnect").status_code == 200


def test_websocket_with_foreign_origin_is_refused() -> None:
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/serial", headers={"Origin": "http://evil.example"}):
            pass


def test_websocket_with_local_origin_works_and_is_cleaned_up() -> None:
    with client.websocket_connect("/ws/serial", headers={"Origin": "http://127.0.0.1:8000"}) as ws:
        assert ws.receive_json()["event"] == "connected"
    assert not active_connections


def test_cors_allows_any_loopback_port_only() -> None:
    ok = client.get("/api/protocols", headers={"Origin": "http://localhost:5173"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert client.get("/api/protocols", headers={"Origin": "http://evil.example"}).status_code == 403


@pytest.mark.parametrize(
    "host,expected",
    [("127.0.0.1", True), ("localhost", True), ("::1", True), ("0.0.0.0", False), ("::", False), ("192.168.1.10", False), ("", False), ("example.com", False)],
)
def test_is_loopback_host(host: str, expected: bool) -> None:
    assert is_loopback_host(host) is expected


def test_launch_ui_server_forces_loopback_with_a_warning(monkeypatch, capsys) -> None:
    import uvicorn
    from omniuart.cli import launch_ui_server

    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, host, port, log_level: seen.update(host=host, port=port))
    assert launch_ui_server(host="192.168.1.10", port=8123, open_browser=False, mode="web") == 0
    assert seen == {"host": "127.0.0.1", "port": 8123}
    assert "local-only" in capsys.readouterr().err
