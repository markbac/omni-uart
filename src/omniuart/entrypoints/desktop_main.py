"""Native Desktop UI Application Binary Entry Point for OmniUART."""

from __future__ import annotations

import sys
from omniuart.ui.desktop import TKINTER_MISSING_MESSAGE, tkinter_available


def run() -> int:
    if not tkinter_available():
        print(f"Error: {TKINTER_MISSING_MESSAGE}", file=sys.stderr)
        return 2
    from omniuart.desktop.app import launch_native_desktop_app

    launch_native_desktop_app()
    return 0


if __name__ == "__main__":
    sys.exit(run())
