"""Native Desktop UI Application Binary Entry Point for OmniUART."""

from __future__ import annotations

import sys
from omniuart.desktop.app import launch_native_desktop_app


def run() -> int:
    launch_native_desktop_app()
    return 0


if __name__ == "__main__":
    sys.exit(run())
