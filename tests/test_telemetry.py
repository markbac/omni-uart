"""Tests for TelemetryBridge: delivery is only reported when it really happened."""

from __future__ import annotations

import asyncio
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from omniuart.core.recorder import PacketEvent
from omniuart.core.telemetry import TelemetryBridge


def _event() -> PacketEvent:
    return PacketEvent(
        direction="rx", raw_hex="AA 55", length_bytes=2, command_name="get_readings",
        decoded_fields={"temperature": 23.5},
    )


@pytest.fixture
def webhook_server():
    received = []
    status = {"code": 200, "fail_first": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers["Content-Length"]))
            code = status["code"]
            if status["fail_first"] > 0:
                status["fail_first"] -= 1
                code = 500
            else:
                received.append(body)
            self.send_response(code)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/t", received, status
    server.shutdown()


def test_webhook_delivers_to_real_server(webhook_server) -> None:
    url, received, _ = webhook_server
    assert TelemetryBridge(webhook_url=url).dispatch(_event())["webhook"] is True
    assert len(received) == 1 and b"get_readings" in received[0]


def test_webhook_retries_with_backoff(webhook_server) -> None:
    url, received, status = webhook_server
    status["fail_first"] = 2
    bridge = TelemetryBridge(webhook_url=url, retries=2, backoff_s=0.01)
    assert bridge.dispatch(_event())["webhook"] is True
    assert len(received) == 1


def test_webhook_failure_is_reported(webhook_server) -> None:
    url, _, status = webhook_server
    status["code"] = 500
    bridge = TelemetryBridge(webhook_url=url, retries=1, backoff_s=0.01)
    assert bridge.dispatch(_event())["webhook"] is False
    assert "500" in bridge.errors["webhook"]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x"])
def test_webhook_rejects_non_http_schemes(url: str) -> None:
    bridge = TelemetryBridge(webhook_url=url)
    assert bridge.dispatch(_event())["webhook"] is False
    assert "scheme" in bridge.errors["webhook"]


def test_dispatch_async_does_not_block_loop(webhook_server) -> None:
    url, received, _ = webhook_server
    result = asyncio.run(TelemetryBridge(webhook_url=url).dispatch_async(_event()))
    assert result["webhook"] is True


def test_mqtt_not_reported_sent_without_client(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "paho", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt", None)
    monkeypatch.setitem(sys.modules, "paho.mqtt.publish", None)
    bridge = TelemetryBridge(mqtt_broker="no-such-host.invalid:1883")
    assert bridge.dispatch(_event())["mqtt"] is False
    assert "paho-mqtt" in bridge.errors["mqtt"]


def test_mqtt_publishes_with_client(monkeypatch) -> None:
    publish = ModuleType("paho.mqtt.publish")
    publish.single = MagicMock()
    mqtt = ModuleType("paho.mqtt"); mqtt.publish = publish
    paho = ModuleType("paho"); paho.mqtt = mqtt
    monkeypatch.setitem(sys.modules, "paho", paho)
    monkeypatch.setitem(sys.modules, "paho.mqtt", mqtt)
    monkeypatch.setitem(sys.modules, "paho.mqtt.publish", publish)
    assert TelemetryBridge(mqtt_broker="mqtt://broker:1884").dispatch(_event())["mqtt"] is True
    args, kwargs = publish.single.call_args
    assert args[0] == "omniuart/telemetry/get_readings"
    assert kwargs["hostname"] == "broker" and kwargs["port"] == 1884


def test_mqtt_broker_error_is_reported(monkeypatch) -> None:
    publish = ModuleType("paho.mqtt.publish")
    publish.single = MagicMock(side_effect=OSError("refused"))
    mqtt = ModuleType("paho.mqtt"); mqtt.publish = publish
    paho = ModuleType("paho"); paho.mqtt = mqtt
    for name, mod in (("paho", paho), ("paho.mqtt", mqtt), ("paho.mqtt.publish", publish)):
        monkeypatch.setitem(sys.modules, name, mod)
    bridge = TelemetryBridge(mqtt_broker="broker")
    assert bridge.dispatch(_event())["mqtt"] is False
    assert "refused" in bridge.errors["mqtt"]
