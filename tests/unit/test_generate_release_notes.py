"""Unit tests for generate_release_notes.py script."""

from __future__ import annotations

import sys
from pathlib import Path

# Add scripts directory to sys.path to import generate_release_notes
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from generate_release_notes import generate_issue_release_notes


def test_generate_issue_release_notes_header_clean() -> None:
    """Verify that release notes generator outputs clean header without 'Keep a Changelog 1.1.0 Format' text."""
    commits = [
        "a1b2c3d feat(#161): add quick action macro buttons",
        "e4f5g6h fix(#160): fix stream recording export",
    ]
    notes = generate_issue_release_notes(commits, version="1.9.0")
    assert "## [1.9.0]" in notes
    assert "Keep a Changelog 1.1.0 Format" not in notes
    assert "### Added" in notes
    assert "### Fixed" in notes
