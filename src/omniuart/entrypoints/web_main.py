"""Web UI Server Binary Entry Point for OmniUART."""

from __future__ import annotations

import sys
from omniuart.cli import launch_ui_server


def run() -> int:
    return launch_ui_server(host="127.0.0.1", port=8000, open_browser=True, mode="web")


if __name__ == "__main__":
    sys.exit(run())
