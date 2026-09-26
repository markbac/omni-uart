"""Tests for structured persistent logging module."""

from __future__ import annotations

import logging
from pathlib import Path
from omniuart.core.logger import setup_logging, DEFAULT_LOG_FILE


def test_setup_logging_creates_file(tmp_path: Path) -> None:
    log_file = tmp_path / "test_run.log"
    logger = setup_logging(log_file=log_file, log_level="DEBUG")
    
    assert logger.name == "omniuart"
    logger.info("Test info message")
    logger.debug("Test debug message")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Test info message" in content
    assert "Test debug message" in content


def test_setup_logging_level_filtering(tmp_path: Path) -> None:
    log_file = tmp_path / "filtered_run.log"
    logger = setup_logging(log_file=log_file, log_level="WARNING")
    
    logger.info("Should not be written")
    logger.warning("Should be written")

    content = log_file.read_text(encoding="utf-8")
    assert "Should not be written" not in content
    assert "Should be written" in content
