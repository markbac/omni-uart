"""Session Replay Engine for OmniUART.

Replays recorded JSON Lines (.jsonl) session packets onto physical or virtual serial transports with timing control.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Union

from omniuart.core.recorder import PacketEvent
from omniuart.core.transport import AsyncTransport

logger = logging.getLogger(__name__)


class SessionReplayer:
    """Replays transaction logs onto a target UART transport."""

    def __init__(self, transport: AsyncTransport, speed_multiplier: float = 1.0) -> None:
        self.transport = transport
        self.speed_multiplier = max(0.1, speed_multiplier)

    async def replay_file(self, jsonl_path: Union[str, Path]) -> int:
        """Replay a recorded .jsonl session log file. Returns count of replayed frames."""
        path = Path(jsonl_path)
        if not path.exists():
            raise FileNotFoundError(f"Session log file not found: {path}")

        events = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    events.append(PacketEvent(**data))

        if not events:
            logger.warning("No events found in session file.")
            return 0

        if not self.transport.is_open:
            await self.transport.open()

        count = 0
        prev_ts: Optional[float] = None

        for event in events:
            if prev_ts is not None:
                delay = (event.timestamp - prev_ts) / self.speed_multiplier
                if delay > 0:
                    await asyncio.sleep(min(delay, 5.0))  # Cap single sleep delay at 5s

            prev_ts = event.timestamp
            hex_clean = event.raw_hex.replace(" ", "")
            if hex_clean and event.direction.lower() == "tx":
                raw_bytes = bytes.fromhex(hex_clean)
                await self.transport.write(raw_bytes)
                count += 1
                logger.info(f"Replayed TX frame ({len(raw_bytes)} bytes): {event.command_name or 'custom'}")

        return count
