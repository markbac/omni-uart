"""Tests for TelemetryBridge module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from omniuart.core.recorder import PacketEvent
from omniuart.core.telemetry import TelemetryBridge


def test_telemetry_bridge_mqtt() -> None:
    bridge = TelemetryBridge(mqtt_broker="mqtt://localhost:1883")
    event = PacketEvent(
        direction="rx",
        raw_hex="AA 55",
        length_bytes=2,
        command_name="get_readings",
        decoded_fields={"temperature": 23.5, "humidity": 45.0},
    )

    res = bridge.dispatch(event)
    assert res["mqtt"] is True
    assert res["webhook"] is False


@patch("urllib.request.urlopen")
def test_telemetry_bridge_webhook(mock_urlopen: MagicMock) -> None:
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    bridge = TelemetryBridge(webhook_url="http://example.com/api/telemetry")
    event = PacketEvent(
        direction="rx",
        raw_hex="AA 55",
        length_bytes=2,
        command_name="get_readings",
        decoded_fields={"temperature": 23.5},
    )

    res = bridge.dispatch(event)
    assert res["webhook"] is True
    assert mock_urlopen.called
