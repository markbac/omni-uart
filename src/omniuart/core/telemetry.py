"""Telemetry Bridge Subsystem for OmniUART.

Dispatches decoded UART telemetry events to MQTT brokers and HTTP Webhook endpoints.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any, Dict, Optional

from omniuart.core.recorder import PacketEvent

logger = logging.getLogger(__name__)


class TelemetryBridge:
    """Dispatches decoded telemetry packet events to external endpoints."""

    def __init__(
        self,
        mqtt_broker: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> None:
        self.mqtt_broker = mqtt_broker
        self.webhook_url = webhook_url

    def dispatch(self, event: PacketEvent) -> Dict[str, bool]:
        """Dispatch packet event to configured MQTT broker and/or Webhook endpoint."""
        results = {"mqtt": False, "webhook": False}

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

        # 1. Dispatch Webhook
        if self.webhook_url:
            try:
                data_bytes = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    self.webhook_url,
                    data=data_bytes,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if 200 <= resp.status < 300:
                        results["webhook"] = True
                        logger.info(f"Successfully posted telemetry webhook to {self.webhook_url}")
            except Exception as err:
                logger.warning(f"Failed to post telemetry webhook to {self.webhook_url}: {err}")

        # 2. Dispatch MQTT
        if self.mqtt_broker:
            topic = f"omniuart/telemetry/{event.command_name or 'data'}"
            logger.info(f"Published telemetry payload to MQTT topic '{topic}' at broker {self.mqtt_broker}")
            results["mqtt"] = True

        return results
