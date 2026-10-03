"""Native Desktop GUI Application Package for OmniUART.

Importing this package does not import ``tkinter``; the GUI classes load on first use so that the CLI,
the web server and the tests work on Python installs without Tk.
"""

from __future__ import annotations

from typing import Any

__all__ = ["OmniUARTDesktopApp", "launch_native_desktop_app"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from omniuart.desktop import app

        return getattr(app, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
