"""Native Desktop Application Launcher for OmniUART."""

from __future__ import annotations

import logging
from omniuart.desktop.app import launch_native_desktop_app

logger = logging.getLogger(__name__)


def launch_desktop_window(url: str = "", title: str = "OmniUART Desktop Workspace", width: int = 1280, height: int = 850) -> None:
    """Launch native desktop application workspace."""
    logger.info("Launching OmniUART Native Desktop Workspace")
    launch_native_desktop_app()
