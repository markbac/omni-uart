"""Tests for Web UI GUI launcher entrypoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from omniuart.cli import main


@patch("omniuart.cli.launch_ui_server")
def test_cli_ui_subcommand(mock_launch: MagicMock) -> None:
    mock_launch.return_value = 0
    res = main(["ui", "--port", "8080", "--no-browser"])
    assert res == 0
    mock_launch.assert_called_once_with(host="127.0.0.1", port=8080, open_browser=False)


@patch("omniuart.cli.launch_ui_server")
def test_cli_zero_args_launches_ui(mock_launch: MagicMock) -> None:
    mock_launch.return_value = 0
    res = main([])
    assert res == 0
    mock_launch.assert_called_once_with(host="127.0.0.1", port=8000, open_browser=True)
