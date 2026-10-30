"""Unit tests for Live Device State Model (#233)."""

import time

from omniuart.core.codec import DecodedFrame
from omniuart.core.device_state import LiveDeviceState, StateValue


def test_state_value_freshness():
    sv = StateValue(field_name="temp", value=23.5, timestamp=time.monotonic(), stale_timeout_s=1.0)
    assert not sv.is_stale
    assert sv.quality == "good"

    sv_old = StateValue(field_name="temp", value=23.5, timestamp=time.monotonic() - 2.0, stale_timeout_s=1.0)
    assert sv_old.is_stale
    assert sv_old.quality == "stale"


def test_live_device_state_update_and_listener():
    state = LiveDeviceState(device_id="sensor_01")
    updates = []

    def on_change(field, val):
        updates.append((field, val.value))

    state.add_listener(on_change)
    state.update_field("temperature", 24.1)

    assert state.connection_online is True
    assert len(updates) == 1
    assert updates[0] == ("temperature", 24.1)

    sv = state.get_field("temperature")
    assert sv is not None
    assert sv.value == 24.1


def test_update_from_decoded_frame():
    state = LiveDeviceState(device_id="sensor_01")
    frame = DecodedFrame(raw=b"123", name="get_readings", fields={"channel": 0, "humidity": 60.5})

    updated = state.update_from_frame(frame)
    assert len(updated) == 2

    snapshot = state.get_state_snapshot()
    assert snapshot["fields"]["get_readings.humidity"]["value"] == 60.5
    assert state.get_field("humidity").value == 60.5
    assert snapshot["connection_online"] is True


def test_mark_connection_lost():
    state = LiveDeviceState(device_id="sensor_01")
    state.update_field("voltage", 3.3)
    assert state.connection_online is True

    state.mark_connection_lost()
    assert state.connection_online is False


def test_plain_name_returns_the_latest_value_from_any_message():
    """#318: values are namespaced per message, and a plain-name read never returns an old value."""
    state = LiveDeviceState(device_id="sensor_01")
    state.update_field("temp", 20.0, namespace="Telemetry")
    state.update_field("temp", 21.0, namespace="Telemetry")
    state.update_field("temp", 99.0, namespace="get_readings")
    assert state.get_field("temp", namespace="Telemetry").value == 21.0
    assert state.get_field("temp").value == 99.0
    assert set(state.get_state_snapshot()["fields"]) == {"Telemetry.temp", "get_readings.temp"}


def test_listener_failures_are_logged_not_swallowed(caplog):
    state = LiveDeviceState(device_id="sensor_01")
    state.add_listener(lambda key, value: 1 / 0)
    state.update_field("temp", 1)
    assert "listener" in caplog.text.lower()
