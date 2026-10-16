"""Tests for structured persistent logging module."""

from __future__ import annotations

import logging
from pathlib import Path

from omniuart.core.logger import setup_logging


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


def test_setup_logging_keeps_stdout_for_command_output(tmp_path: Path, capsys) -> None:
    logger = setup_logging(log_file=tmp_path / "console.log", log_level="INFO")

    logging.getLogger("omniuart.core.session").info("Child logger record")

    captured = capsys.readouterr()
    assert "Child logger record" in captured.err
    assert "Child logger record" not in captured.out
    assert logger.propagate is False


def test_setup_logging_falls_back_to_console_when_file_cannot_open(tmp_path: Path, capsys) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("", encoding="utf-8")

    logger = setup_logging(log_file=blocker / "omniuart.log", log_level="INFO")
    logger.info("Still logged")

    assert "Still logged" in capsys.readouterr().err
