"""Logging set-up for OmniUART entry points, built on ctxlogkit.

Entry points (the CLI, the batch script runner, the web UI server and the simulator) call
``setup_logging`` once. It configures the ``omniuart`` logger, so every module that uses
``logging.getLogger(__name__)`` inherits its console and rotating-file handlers.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from ctxlogkit import setup_logging as _ctx_setup_logging

DEFAULT_LOG_DIR = Path.home() / ".omniuart" / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "omniuart.log"
LOGGER_NAME = "omniuart"


def setup_logging(
    log_file: Optional[Path | str] = None,
    log_level: str = "INFO",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
    to_file: bool = True,
) -> logging.Logger:
    """Configure the ``omniuart`` logger with a console handler and a rotating log file.

    Log records go to standard error, so they never mix with the command output on standard
    output. When the log file cannot be opened, logging carries on with the console alone.
    """
    target_file = Path(log_file) if log_file else DEFAULT_LOG_FILE

    def configure(file_path: Optional[Path]) -> logging.Logger:
        return _ctx_setup_logging(
            name=LOGGER_NAME,
            level=log_level.upper(),
            console_stream=sys.stderr,
            use_emoji=False,
            to_file=file_path is not None,
            file_path=str(file_path) if file_path is not None else None,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )

    if not to_file:
        return configure(None)
    try:
        return configure(target_file)
    except OSError as err:
        logger = configure(None)
        logger.warning("Could not initialize log file at %s: %s", target_file, err)
        return logger
