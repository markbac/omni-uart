"""Unit tests for Live Device State Model (#233)."""

import time
import pytest

from omniuart.core.codec import DecodedFrame
from omniuart.core.device_state import LiveDeviceState, StateValue


def test_state_value_freshness():
    sv = StateValue(field_name="temp", value=23.5, timestamp=time.time(), stale_timeout_s=1.0)
    assert not sv.is_stale
    assert sv.quality == "good"

    sv_old = StateValue(field_name="temp", value=23.5, timestamp=time.time() - 2.0, stale_timeout_s=1.0)
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
    assert snapshot["fields"]["humidity"]["value"] == 60.5
    assert snapshot["connection_online"] is True


def test_mark_connection_lost():
    state = LiveDeviceState(device_id="sensor_01")
    state.update_field("voltage", 3.3)
    assert state.connection_online is True

    state.mark_connection_lost()
    assert state.connection_online is False
