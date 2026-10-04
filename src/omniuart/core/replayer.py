"""Session Replay Engine for OmniUART.

Replays recorded JSON Lines (.jsonl) session packets onto physical or virtual serial transports with timing control.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Union

from omniuart.core.limits import get_limits
from omniuart.core.recorder import PacketEvent
from omniuart.core.transport import AsyncTransport

logger = logging.getLogger(__name__)


from enum import Enum


class ReplayTimingMode(str, Enum):
    """Timing policies for session replay."""

    FAITHFUL = "faithful"  # Exact inter-packet delays without artificial capping
    CAPPED = "capped"  # Inter-packet delays capped at max_gap_s (default 5.0 s)
    ACCELERATED = "accelerated"  # High-speed accelerated replay
    FIXED_RATE = "fixed_rate"  # Uniform interval between packets (fixed_interval_s)
    DETERMINISTIC = "deterministic"  # Immediate zero-delay replay for tests


class ReplayDirectionMode(str, Enum):
    """Direction filtering / emulation mode for replay."""

    TX_ONLY = "tx_only"  # Replay outbound TX frames only (default)
    BIDIRECTIONAL = "bidirectional"  # Replay both TX and RX frames in timestamp order
    RX_EMULATE = "rx_emulate"  # Replay inbound RX frames (emulating target device)


class SessionReplayer:
    """Replays transaction logs onto a target UART transport with configurable timing and direction control."""

    def __init__(
        self,
        transport: AsyncTransport,
        timing_mode: Union[ReplayTimingMode, str] = ReplayTimingMode.CAPPED,
        direction_mode: Union[ReplayDirectionMode, str] = ReplayDirectionMode.TX_ONLY,
        speed_multiplier: float = 1.0,
        max_gap_s: Optional[float] = 5.0,
        fixed_interval_s: float = 0.01,
        max_duration_s: Optional[float] = None,
    ) -> None:
        self.transport = transport
        self.timing_mode = ReplayTimingMode(timing_mode) if isinstance(timing_mode, str) else timing_mode
        self.direction_mode = ReplayDirectionMode(direction_mode) if isinstance(direction_mode, str) else direction_mode
        self.speed_multiplier = max(0.0, float(speed_multiplier))
        self.max_gap_s = max_gap_s
        self.fixed_interval_s = fixed_interval_s
        self.max_duration_s = max_duration_s if max_duration_s is not None else get_limits().replay_duration_s

    async def replay_file(self, jsonl_path: Union[str, Path]) -> int:
        """Replay a recorded .jsonl session log file. Returns count of replayed frames."""
        path = Path(jsonl_path)
        if not path.exists():
            raise FileNotFoundError(f"Session log file not found: {path}")

        events = []
        with path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line_str = line.strip()
                if line_str:
                    try:
                        data = json.loads(line_str)
                        events.append(PacketEvent(**data))
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Line {line_num}: invalid JSON in session log '{path.name}': {exc.msg}") from exc
                    except Exception as exc:
                        raise ValueError(f"Line {line_num}: invalid packet event in session log '{path.name}': {exc}") from exc

        if not events:
            logger.warning("No events found in session file.")
            return 0

        if not self.transport.is_open:
            await self.transport.open()

        count = 0
        prev_ts: Optional[float] = None
        waited = 0.0

        for event in events:
            hex_clean = event.raw_hex.replace(" ", "")
            if not hex_clean:
                continue

            dir_low = event.direction.lower()
            should_replay = (
                (self.direction_mode == ReplayDirectionMode.TX_ONLY and dir_low == "tx")
                or (self.direction_mode == ReplayDirectionMode.RX_EMULATE and dir_low == "rx")
                or (self.direction_mode == ReplayDirectionMode.BIDIRECTIONAL)
            )
            if not should_replay:
                continue

            delay = 0.0
            if prev_ts is not None:
                if self.timing_mode == ReplayTimingMode.DETERMINISTIC or self.speed_multiplier == 0:
                    delay = 0.0
                elif self.timing_mode == ReplayTimingMode.FIXED_RATE:
                    delay = self.fixed_interval_s / max(0.001, self.speed_multiplier)
                else:  # FAITHFUL, CAPPED, ACCELERATED
                    raw_delay = (event.timestamp - prev_ts) / self.speed_multiplier
                    if self.timing_mode == ReplayTimingMode.CAPPED and self.max_gap_s is not None:
                        delay = min(raw_delay, self.max_gap_s)
                        if raw_delay > self.max_gap_s:
                            logger.info("Inter-packet gap of %.2f s capped to %.2f s maximum", raw_delay, self.max_gap_s)
                    elif self.max_gap_s is not None:
                        delay = min(raw_delay, self.max_gap_s)
                    else:
                        delay = raw_delay

            if delay > 0:
                if waited + delay > self.max_duration_s:
                    logger.warning("Replay stopped after %d frame(s): it would exceed the %g s duration limit", count, self.max_duration_s)
                    break
                await asyncio.sleep(delay)
                waited += delay

            prev_ts = event.timestamp
            raw_bytes = bytes.fromhex(hex_clean)
            await self.transport.write(raw_bytes)
            count += 1
            logger.info(f"Replayed {dir_low.upper()} frame ({len(raw_bytes)} bytes): {event.command_name or 'custom'}")

        return count


