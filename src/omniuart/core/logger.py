"""Structured Persistent Logging module for OmniUART.

Provides file rotation, custom log paths, log levels, and console formatting.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

DEFAULT_LOG_DIR = Path.home() / ".omniuart" / "logs"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "omniuart.log"


def setup_logging(
    log_file: Optional[Path | str] = None,
    log_level: str = "INFO",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure structured logging with RotatingFileHandler and stream handler."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger("omniuart")
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    target_file = Path(log_file) if log_file else DEFAULT_LOG_FILE
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            target_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as err:
        sys_logger = logging.getLogger("omniuart.logger")
        sys_logger.warning(f"Could not initialize log file at {target_file}: {err}")

    return root_logger
