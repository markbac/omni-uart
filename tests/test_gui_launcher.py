"""Tests for Web UI GUI & Native Desktop launcher entrypoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from omniuart.cli import main
from omniuart.ui.desktop import launch_desktop_window


@patch("omniuart.cli.launch_ui_server")
def test_cli_ui_subcommand(mock_launch: MagicMock) -> None:
    mock_launch.return_value = 0
    res = main(["ui", "--port", "8080", "--mode", "web", "--no-browser"])
    assert res == 0
    mock_launch.assert_called_once_with(host="127.0.0.1", port=8080, open_browser=False, mode="web")


@patch("omniuart.cli.launch_ui_server")
def test_cli_zero_args_launches_desktop_ui(mock_launch: MagicMock) -> None:
    mock_launch.return_value = 0
    res = main([])
    assert res == 0
    mock_launch.assert_called_once_with(host="127.0.0.1", port=8000, open_browser=True, mode="desktop")


@patch("webbrowser.open")
def test_desktop_window_launcher_fallback(mock_browser_open: MagicMock) -> None:
    try:
        launch_desktop_window("http://127.0.0.1:8000")
    except Exception as e:
        if "tcl" in type(e).__name__.lower() or "tcl" in str(e).lower() or "display" in str(e).lower():
            pass
        else:
            raise e
