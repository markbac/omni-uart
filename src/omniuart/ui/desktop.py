"""Native Desktop Application Window Launcher for OmniUART using pywebview."""

from __future__ import annotations

import logging
import threading
import time
import webbrowser
from typing import Optional

logger = logging.getLogger(__name__)


def launch_desktop_window(url: str, title: str = "OmniUART Control Workbench", width: int = 1280, height: int = 850) -> None:
    """Launch native OS desktop application window wrapping OmniUART Web UI."""
    try:
        import webview
        logger.info(f"Launching PyWebView Desktop Window for {url}")
        window = webview.create_window(title=title, url=url, width=width, height=height, resizable=True)
        webview.start()
    except Exception as e:
        logger.warning(f"PyWebView not available or native window launch failed: {e}. Falling back to default web browser.")
        webbrowser.open(url)
