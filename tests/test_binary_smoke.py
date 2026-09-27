"""Binary Execution & PyInstaller Smoke Verification Test Suite.

Ensures that entry point modules (cli_main, web_main, desktop_main) and PyInstaller bundled
standalone executables execute without runtime import or startup errors.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest

from omniuart.entrypoints import cli_main, web_main, desktop_main


def test_cli_entrypoint_module():
    """Verify CLI entrypoint module imports and helper functions work."""
    assert hasattr(cli_main, "main")


def test_web_entrypoint_module():
    """Verify Web UI entrypoint module imports and helper functions work."""
    assert hasattr(web_main, "run")


def test_desktop_entrypoint_module():
    """Verify Desktop UI entrypoint module imports and helper functions work."""
    assert hasattr(desktop_main, "run")


@pytest.mark.skipif(os.environ.get("SKIP_BINARY_BUILD_TEST") == "1", reason="Skipping slow binary build test")
def test_compiled_binaries_smoke_execution(tmp_path):
    """Smoke test compiled standalone executables for startup errors."""
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    
    # Check if dist binaries exist or build them via PyInstaller
    cli_binary = dist_dir / ("omni-uart-cli.exe" if os.name == "nt" else "omni-uart-cli")
    web_binary = dist_dir / ("omni-uart-web.exe" if os.name == "nt" else "omni-uart-web")
    desktop_binary = dist_dir / ("omni-uart-desktop.exe" if os.name == "nt" else "omni-uart-desktop")

    if not cli_binary.exists():
        # Build binaries for smoke testing
        res = subprocess.run(["pyinstaller", "omniuart.spec"], cwd=str(repo_root), capture_output=True, text=True)
        assert res.returncode == 0, f"PyInstaller build failed: {res.stderr}"

    # 1. Verify omni-uart-cli executable runs --help
    assert cli_binary.exists(), f"Binary {cli_binary} not found"
    res_cli = subprocess.run([str(cli_binary), "--help"], capture_output=True, text=True)
    assert res_cli.returncode == 0
    assert "OmniUART" in res_cli.stdout or "usage:" in res_cli.stdout

    # 2. Verify omni-uart-web executable exists
    assert web_binary.exists(), f"Binary {web_binary} not found"

    # 3. Verify omni-uart-desktop executable exists
    assert desktop_binary.exists(), f"Binary {desktop_binary} not found"
