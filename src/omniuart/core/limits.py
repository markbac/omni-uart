"""Resource limits for parsing and running untrusted definitions, scripts, captures and streams.

Every limit has a conservative default and can be raised or lowered with an environment variable
``OMNIUART_MAX_<NAME>`` (for example ``OMNIUART_MAX_FRAME_BYTES=4096``). A value that is not a positive
number is ignored with a warning, never silently treated as "unlimited".
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, fields
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Limits:
    definition_bytes: int = 1_048_576  # size of a protocol or script file/text
    frame_bytes: int = 1_048_576  # largest frame the codec will wait for; also the largest declared field length
    script_steps: int = 10_000
    script_duration_s: float = 3600.0
    replay_duration_s: float = 3600.0
    fuzz_vectors: int = 10_000
    retries: int = 10


def get_limits() -> Limits:
    """The defaults with any ``OMNIUART_MAX_*`` environment overrides applied."""
    values: Dict[str, Any] = {}
    for f in fields(Limits):
        raw = os.environ.get(f"OMNIUART_MAX_{f.name.upper()}")
        if raw is None:
            continue
        try:
            number = float(raw) if f.type == "float" else int(raw)
            if number <= 0:
                raise ValueError
        except ValueError:
            logger.warning("Ignoring invalid OMNIUART_MAX_%s=%r (must be a positive number)", f.name.upper(), raw)
            continue
        values[f.name] = number
    return Limits(**values)
