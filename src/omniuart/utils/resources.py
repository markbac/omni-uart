"""Resource path resolution helper for development and PyInstaller standalone binary execution mode."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Union


def get_resource_path(relative_path: Union[str, Path]) -> Path:
    """Resolve absolute path to resource, handling PyInstaller _MEIPASS bundle redirection."""
    rel = Path(relative_path)
    
    # PyInstaller creates a temp folder and stores path in _MEIPASS
    if hasattr(sys, "_MEIPASS"):
        bundle_dir = Path(getattr(sys, "_MEIPASS"))
        candidate = bundle_dir / rel
        if candidate.exists():
            return candidate

    # Development mode fallback
    dev_dir = Path(__file__).parent.parent.parent.parent
    candidate_dev = dev_dir / rel
    if candidate_dev.exists():
        return candidate_dev

    # Local fallback
    return Path.cwd() / rel
