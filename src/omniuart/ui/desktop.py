"""Native Desktop Application Launcher for OmniUART."""

from __future__ import annotations

import importlib.util
import logging

logger = logging.getLogger(__name__)

TKINTER_MISSING_MESSAGE = (
    "The desktop interface needs tkinter, which is not installed for this Python.\n"
    "Install it (for example 'sudo apt install python3-tk' on Debian/Ubuntu, or use a Python build that includes Tk), "
    "or use the web interface with: omni-uart ui --mode web"
)


def tkinter_available() -> bool:
    """Whether the Tk bindings can be imported."""
    import sys
    if sys.modules.get("tkinter") is None:
        return False
    try:
        import tkinter
        return True
    except (ImportError, ValueError, AttributeError, Exception):
        return False


def launch_desktop_window(url: str = "", title: str = "OmniUART Desktop Workspace", width: int = 1280, height: int = 850) -> None:
    """Launch native desktop application workspace."""
    if not tkinter_available():
        raise RuntimeError(TKINTER_MISSING_MESSAGE)
    from omniuart.desktop.app import launch_native_desktop_app

    logger.info("Launching OmniUART Native Desktop Workspace")
    launch_native_desktop_app()
