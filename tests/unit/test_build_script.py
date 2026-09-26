"""Unit tests for build script availability and syntax."""

from pathlib import Path
import pytest


def test_build_standalone_script_exists() -> None:
    """Verify that build_standalone.ps1 script exists and contains expected commands."""
    script_path = Path("scripts/build_standalone.ps1")
    assert script_path.exists()
    content = script_path.read_text(encoding="utf-8")
    assert "pyinstaller" in content.lower()
    assert "dist/omni-uart.exe" in content.lower()
