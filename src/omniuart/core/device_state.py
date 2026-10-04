"""Live Device State Model Subsystem for OmniUART (#233).

Maintains a coherent live in-memory model of device state derived from reads, responses, unsolicited telemetry,
and events. Manages data freshness, stale/unknown state determination, connection loss, and change listeners.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from omniuart.core.codec import DecodedFrame


@dataclass
class StateValue:
    """Individual state value with timestamp and data quality status."""

    field_name: str
    value: Any
    timestamp: float
    stale_timeout_s: float = 30.0

    @property
    def age_s(self) -> float:
        return time.time() - self.timestamp

    @property
    def is_stale(self) -> bool:
        return self.age_s > self.stale_timeout_s

    @property
    def quality(self) -> str:
        if self.is_stale:
            return "stale"
        return "good"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "timestamp": self.timestamp,
            "age_s": round(self.age_s, 2),
            "quality": self.quality,
            "is_stale": self.is_stale,
        }


class LiveDeviceState:
    """Live in-memory state repository for a connected or target device."""

    def __init__(self, device_id: str, default_stale_s: float = 30.0) -> None:
        self.device_id = device_id
        self.default_stale_s = default_stale_s
        self.values: Dict[str, StateValue] = {}
        self.connection_online: bool = False
        self.listeners: List[Callable[[str, StateValue], None]] = []

    def add_listener(self, callback: Callable[[str, StateValue], None]) -> None:
        """Register a callback for state value changes."""
        self.listeners.append(callback)

    def notify_listeners(self, field_name: str, state_val: StateValue) -> None:
        for listener in self.listeners:
            try:
                listener(field_name, state_val)
            except Exception:
                pass

    def update_field(self, field_name: str, value: Any, timestamp: Optional[float] = None, stale_timeout_s: Optional[float] = None) -> StateValue:
        """Update a specific state field and notify listeners."""
        ts = timestamp if timestamp is not None else time.time()
        timeout = stale_timeout_s if stale_timeout_s is not None else self.default_stale_s

        state_val = StateValue(field_name=field_name, value=value, timestamp=ts, stale_timeout_s=timeout)
        self.values[field_name] = state_val
        self.connection_online = True
        self.notify_listeners(field_name, state_val)
        return state_val

    def update_from_frame(self, frame: DecodedFrame, timestamp: Optional[float] = None) -> List[StateValue]:
        """Update state model automatically from decoded frame fields."""
        if not frame.ok or not frame.fields:
            return []

        ts = timestamp if timestamp is not None else time.time()
        updated = []
        for name, val in frame.fields.items():
            updated.append(self.update_field(name, val, timestamp=ts))
        return updated

    def get_field(self, field_name: str) -> Optional[StateValue]:
        """Retrieve state value for field."""
        return self.values.get(field_name)

    def mark_connection_lost(self) -> None:
        """Mark device connection as offline/lost."""
        self.connection_online = False

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get dict snapshot of all active device state values."""
        return {
            "device_id": self.device_id,
            "connection_online": self.connection_online,
            "fields": {name: s.to_dict() for name, s in self.values.items()},
        }
