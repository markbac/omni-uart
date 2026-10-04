"""Telemetry Bridge Subsystem for OmniUART.

Dispatches decoded UART telemetry events to MQTT brokers and HTTP Webhook endpoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from omniuart.core.limits import get_limits
from omniuart.core.recorder import PacketEvent

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Instrumentation metrics for throughput, latencies, error counts and queues (#223)."""

    tx_bytes: int = 0
    rx_bytes: int = 0
    decoded_frames: int = 0
    total_decode_latency_ms: float = 0.0
    min_decode_latency_ms: float = float("inf")
    max_decode_latency_ms: float = 0.0
    total_transport_latency_ms: float = 0.0
    min_transport_latency_ms: float = float("inf")
    max_transport_latency_ms: float = 0.0
    timeouts: int = 0
    retries: int = 0
    errors: int = 0
    queue_depth: int = 0

    @property
    def avg_decode_latency_ms(self) -> float:
        return self.total_decode_latency_ms / max(1, self.decoded_frames)

    @property
    def avg_transport_latency_ms(self) -> float:
        total_ops = self.decoded_frames + self.timeouts + self.errors
        return self.total_transport_latency_ms / max(1, total_ops)

    def to_dict(self) -> Dict[str, Any]:
        limits = get_limits()
        return {
            "tx_bytes": self.tx_bytes,
            "rx_bytes": self.rx_bytes,
            "decoded_frames": self.decoded_frames,
            "decode_latency_ms": {
                "total": round(self.total_decode_latency_ms, 3),
                "avg": round(self.avg_decode_latency_ms, 3),
                "min": round(self.min_decode_latency_ms if self.decoded_frames > 0 else 0.0, 3),
                "max": round(self.max_decode_latency_ms, 3),
            },
            "transport_latency_ms": {
                "total": round(self.total_transport_latency_ms, 3),
                "avg": round(self.avg_transport_latency_ms, 3),
                "min": round(self.min_transport_latency_ms if self.total_transport_latency_ms > 0 else 0.0, 3),
                "max": round(self.max_transport_latency_ms, 3),
            },
            "timeouts": self.timeouts,
            "retries": self.retries,
            "errors": self.errors,
            "queue_depth": self.queue_depth,
            "resource_limits": {
                "max_retries": limits.retries,
                "script_duration_s": limits.script_duration_s,
                "frame_bytes": limits.frame_bytes,
            },
        }


class MetricsCollector:
    """Thread-safe collector for performance profiling telemetry (#223)."""

    def __init__(self) -> None:
        self.metrics = PerformanceMetrics()

    def record_tx(self, count: int) -> None:
        self.metrics.tx_bytes += count

    def record_rx(self, count: int) -> None:
        self.metrics.rx_bytes += count

    def record_decode(self, latency_ms: float) -> None:
        self.metrics.decoded_frames += 1
        self.metrics.total_decode_latency_ms += latency_ms
        if latency_ms < self.metrics.min_decode_latency_ms:
            self.metrics.min_decode_latency_ms = latency_ms
        if latency_ms > self.metrics.max_decode_latency_ms:
            self.metrics.max_decode_latency_ms = latency_ms

    def record_transport_latency(self, latency_ms: float) -> None:
        self.metrics.total_transport_latency_ms += latency_ms
        if latency_ms < self.metrics.min_transport_latency_ms:
            self.metrics.min_transport_latency_ms = latency_ms
        if latency_ms > self.metrics.max_transport_latency_ms:
            self.metrics.max_transport_latency_ms = latency_ms

    def record_timeout(self) -> None:
        self.metrics.timeouts += 1

    def record_retry(self) -> None:
        self.metrics.retries += 1

    def record_error(self) -> None:
        self.metrics.errors += 1

    def update_queue_depth(self, depth: int) -> None:
        self.metrics.queue_depth = depth

    def snapshot(self) -> Dict[str, Any]:
        return self.metrics.to_dict()


ALLOWED_WEBHOOK_SCHEMES = ("http", "https")
WEBHOOK_TIMEOUT_S = 2.0


def _parse_broker(broker: str) -> Tuple[str, int]:
    """Split ``host``, ``host:port`` or ``mqtt://host:port`` into (host, port)."""
    parsed = urlparse(broker if "://" in broker else f"mqtt://{broker}")
    if not parsed.hostname:
        raise ValueError(f"invalid MQTT broker '{broker}'")
    return parsed.hostname, parsed.port or 1883


class TelemetryBridge:
    """Dispatches decoded telemetry packet events to external endpoints.

    ``dispatch`` returns, per endpoint, whether delivery really succeeded; ``errors`` holds the reason
    for each endpoint that was configured but failed. MQTT needs the optional ``paho-mqtt`` package
    (``pip install omni-uart[mqtt]``); without it MQTT delivery is reported as failed, never as sent.
    """

    def __init__(
        self,
        mqtt_broker: Optional[str] = None,
        webhook_url: Optional[str] = None,
        retries: int = 2,
        backoff_s: float = 0.2,
    ) -> None:
        self.mqtt_broker = mqtt_broker
        self.webhook_url = webhook_url
        self.retries = min(max(0, retries), get_limits().retries)
        self.backoff_s = backoff_s
        self.errors: Dict[str, str] = {}

    async def dispatch_async(self, event: PacketEvent) -> Dict[str, bool]:
        """Run :meth:`dispatch` off the event loop (it blocks on network I/O)."""
        return await asyncio.to_thread(self.dispatch, event)

    def _post_webhook(self, data: bytes) -> None:
        scheme = urlparse(self.webhook_url or "").scheme.lower()
        if scheme not in ALLOWED_WEBHOOK_SCHEMES:
            raise ValueError(f"webhook URL scheme '{scheme}' is not allowed (use http or https)")
        last: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(
                    self.webhook_url or "", data=data, headers={"Content-Type": "application/json"}, method="POST"
                )
                with urllib.request.urlopen(req, timeout=WEBHOOK_TIMEOUT_S) as resp:
                    if 200 <= resp.status < 300:
                        return
                    last = RuntimeError(f"HTTP {resp.status}")
            except Exception as err:  # noqa: BLE001 - reported to the caller
                last = err
            if attempt < self.retries:
                time.sleep(self.backoff_s * (2**attempt))
        raise RuntimeError(str(last))

    def _publish_mqtt(self, topic: str, data: bytes) -> None:
        try:
            import paho.mqtt.publish as publish  # type: ignore[import-untyped,import-not-found,unused-ignore]
        except ImportError as exc:
            raise RuntimeError("MQTT needs the optional 'paho-mqtt' package (pip install omni-uart[mqtt])") from exc
        host, port = _parse_broker(self.mqtt_broker or "")
        publish.single(topic, payload=data, hostname=host, port=port)

    def dispatch(self, event: PacketEvent) -> Dict[str, bool]:
        """Deliver the event to the configured endpoints; a result is True only if delivery succeeded."""
        results = {"mqtt": False, "webhook": False}
        self.errors = {}

        if not event.decoded_fields:
            return results

        payload = {
            "timestamp": event.timestamp,
            "direction": event.direction,
            "command_name": event.command_name or "unknown",
            "command_id": event.command_id,
            "fields": event.decoded_fields,
            "crc_valid": event.crc_valid,
        }
        data = json.dumps(payload).encode("utf-8")

        if self.webhook_url:
            try:
                self._post_webhook(data)
                results["webhook"] = True
            except Exception as err:  # noqa: BLE001
                self.errors["webhook"] = str(err)
                logger.warning("Failed to post telemetry webhook to %s: %s", self.webhook_url, err)

        if self.mqtt_broker:
            topic = f"omniuart/telemetry/{event.command_name or 'data'}"
            try:
                self._publish_mqtt(topic, data)
                results["mqtt"] = True
            except Exception as err:  # noqa: BLE001
                self.errors["mqtt"] = str(err)
                logger.warning("Failed to publish telemetry to MQTT broker %s: %s", self.mqtt_broker, err)

        return results
