"""The web interface and CLI must work when tkinter is not installed."""

from __future__ import annotations

import subprocess
import sys

BLOCK = "import sys; sys.modules['tkinter'] = None; "


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", BLOCK + code], capture_output=True, text=True, timeout=60)


def test_core_cli_and_web_import_without_tkinter() -> None:
    result = _run("import omniuart.cli, omniuart.ui.app, omniuart.desktop, omniuart.core.codec; print('ok')")
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_desktop_mode_reports_missing_tkinter() -> None:
    result = _run(
        "from omniuart.cli import launch_ui_server; "
        "print(launch_ui_server(mode='desktop'))"
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("2")
    assert "tkinter" in result.stderr
    assert "--mode web" in result.stderr


def test_desktop_entrypoint_reports_missing_tkinter() -> None:
    result = _run("from omniuart.entrypoints.desktop_main import run; print(run())")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("2")
    assert "tkinter" in result.stderr
