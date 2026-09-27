"""Tests for expanded GitHub Pages site generator."""

from __future__ import annotations

from pathlib import Path
from omniuart.docs_generator import build_site_documentation


def test_build_site_documentation_includes_schemas_and_manuals(tmp_path: Path) -> None:
    out_dir = tmp_path / "_site"
    site_path = build_site_documentation(out_dir)

    assert site_path.exists()
    assert (site_path / "index.html").exists()

    index_content = (site_path / "index.html").read_text(encoding="utf-8")
    assert "About OmniUART" in index_content
    assert "release/guidance.html" in index_content
    assert "protocols/index.html" in index_content

    assert (site_path / "protocols" / "index.html").exists()
    proto_catalog_content = (site_path / "protocols" / "index.html").read_text(encoding="utf-8")
    assert "Discovered Hardware Protocols" in proto_catalog_content

