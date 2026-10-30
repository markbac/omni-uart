"""Resource path resolution helper for development, installed packages, and PyInstaller standalone binary execution mode."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Union


def get_resource_path(relative_path: Union[str, Path]) -> Path:
    """Resolve absolute path to resource, handling package resources and PyInstaller _MEIPASS bundle redirection."""
    rel = Path(relative_path)

    # 1. PyInstaller creates a temp folder and stores path in _MEIPASS
    if hasattr(sys, "_MEIPASS"):
        bundle_dir = Path(getattr(sys, "_MEIPASS"))  # noqa: B009 - not a typed attribute
        candidate = bundle_dir / rel
        if candidate.exists():
            return candidate

    # 2. Packaged resources inside omniuart wheel installation
    try:
        from importlib.resources import files
        pkg_root = Path(str(files("omniuart")))
        candidate_pkg = pkg_root / rel
        if candidate_pkg.exists():
            return candidate_pkg
    except Exception:
        pass

    # 3. Development mode fallback (relative to src/omniuart/utils/resources.py)
    dev_dir = Path(__file__).resolve().parent.parent.parent.parent
    candidate_dev = dev_dir / rel
    if candidate_dev.exists():
        return candidate_dev

    # 4. Local fallback
    return Path.cwd() / rel
