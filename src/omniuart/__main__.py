"""Module execution entry point: python -m omniuart."""

from __future__ import annotations

import sys
from omniuart.cli import main

if __name__ == "__main__":
    sys.exit(main())
