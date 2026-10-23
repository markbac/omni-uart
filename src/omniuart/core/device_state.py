"""Live Device State Model Subsystem for OmniUART (#233, #318).

Maintains a coherent live in-memory model of device state derived from reads, responses, unsolicited telemetry,
and events. Manages data freshness, monotonic staleness, connection loss, namespacing, and change listeners.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from omniuart.core.codec import DecodedFrame

logger = logging.getLogger(__name__)


@dataclass
class StateValue:
    """Individual state value with monotonic timestamp and data quality status (#233, #318)."""

    field_name: str
    value: Any
    timestamp: float
    stale_timeout_s: float = 30.0
    namespace: Optional[str] = None
    connection_online: bool = True

    @property
    def key(self) -> str:
        return f"{self.namespace}.{self.field_name}" if self.namespace else self.field_name

    @property
    def age_s(self) -> float:
        now = time.time() if self.timestamp > 1e8 else time.monotonic()
        return max(0.0, now - self.timestamp)

    @property
    def is_stale(self) -> bool:
        if not self.connection_online:
            return True
        return self.age_s > self.stale_timeout_s

    @property
    def quality(self) -> str:
        if not self.connection_online:
            return "offline"
        if self.is_stale:
            return "stale"
        return "good"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "field_name": self.field_name,
            "namespace": self.namespace,
            "value": self.value,
            "timestamp": self.timestamp,
            "age_s": round(self.age_s, 2),
            "quality": self.quality,
            "is_stale": self.is_stale,
            "connection_online": self.connection_online,
        }


class LiveDeviceState:
    """Live in-memory state repository for a connected or target device (#233, #318)."""

    def __init__(self, device_id: str, default_stale_s: float = 30.0) -> None:
        self.device_id = device_id
        self.default_stale_s = default_stale_s
        self.values: Dict[str, StateValue] = {}
        self.connection_online: bool = False
        self.listeners: List[Callable[[str, StateValue], None]] = []

    def add_listener(self, callback: Callable[[str, StateValue], None]) -> None:
        """Register a callback for state value changes."""
        self.listeners.append(callback)

    def notify_listeners(self, key: str, state_val: StateValue) -> None:
        """Notify listeners of value changes, logging any errors rather than swallowing silently (#318)."""
        for listener in self.listeners:
            try:
                listener(key, state_val)
            except Exception as e:
                logger.exception("State change listener error for key %s: %s", key, e)

    def update_field(
        self,
        field_name: str,
        value: Any,
        namespace: Optional[str] = None,
        timestamp: Optional[float] = None,
        stale_timeout_s: Optional[float] = None,
    ) -> StateValue:
        """Update a state field (with optional namespace) and notify listeners (#318)."""
        ts = timestamp if timestamp is not None else time.monotonic()
        timeout = stale_timeout_s if stale_timeout_s is not None else self.default_stale_s

        key = f"{namespace}.{field_name}" if namespace else field_name
        state_val = StateValue(
            field_name=field_name,
            value=value,
            timestamp=ts,
            stale_timeout_s=timeout,
            namespace=namespace,
            connection_online=True,
        )
        self.values[key] = state_val
        if namespace and field_name not in self.values:
            self.values[field_name] = state_val
        self.connection_online = True
        self.notify_listeners(key, state_val)
        return state_val

    def update_from_frame(
        self,
        frame: DecodedFrame,
        timestamp: Optional[float] = None,
        use_namespace: bool = True,
    ) -> List[StateValue]:
        """Update state model from decoded frame, namespacing by command/message to prevent collision (#318)."""
        if not frame.ok or not frame.fields:
            return []

        ts = timestamp if timestamp is not None else time.monotonic()
        ns = (frame.name or "frame") if use_namespace else None
        updated = []
        for name, val in frame.fields.items():
            updated.append(self.update_field(name, val, namespace=ns, timestamp=ts))
        return updated

    def get_field(self, field_name: str, namespace: Optional[str] = None) -> Optional[StateValue]:
        """Retrieve state value for field, checking namespaced key then bare field (#318)."""
        if namespace:
            key = f"{namespace}.{field_name}"
            if key in self.values:
                return self.values[key]
        if field_name in self.values:
            return self.values[field_name]
        # Suffix matching fallback
        for k, v in self.values.items():
            if k.endswith(f".{field_name}"):
                return v
        return None

    def mark_connection_lost(self) -> None:
        """Mark device connection as offline and update all stored values to offline quality (#318)."""
        self.connection_online = False
        for val in self.values.values():
            val.connection_online = False

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get dict snapshot of all active device state values."""
        return {
            "device_id": self.device_id,
            "connection_online": self.connection_online,
            "fields": {key: s.to_dict() for key, s in self.values.items()},
        }
