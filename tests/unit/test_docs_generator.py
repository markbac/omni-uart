"""Unit tests for docs_generator and CLI docs subcommand."""

import tempfile
from pathlib import Path
import pytest

from omniuart.cli import main as cli_main
from omniuart.core.catalog import CatalogManager
from omniuart.docs_generator import (
    build_site_documentation,
    generate_html_docs,
    generate_markdown_docs,
)


def test_generate_markdown_and_html_docs() -> None:
    """Verify generating Markdown and HTML documentation for a protocol."""
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node")
    assert spec is not None

    md = generate_markdown_docs(spec)
    assert f"# Hardware Protocol Specification: {spec.metadata.name}" in md
    assert "Command Catalog & Message Signatures" in md

    html_str = generate_html_docs(spec)
    assert "<!DOCTYPE html>" in html_str
    assert spec.metadata.name in html_str


def test_build_site_documentation() -> None:
    """Verify building complete documentation site for all discovered protocols."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        site_dir = build_site_documentation(tmp_path)
        
        assert site_dir.exists()
        assert (site_dir / "index.html").exists()

        index_html = (site_dir / "index.html").read_text(encoding="utf-8")
        assert "⚡ OmniUART Hardware Protocol Specification Hub" in index_html
        assert "BinarySensorNode" in index_html


def test_cli_docs_command() -> None:
    """Verify CLI docs command execution."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        exit_code = cli_main(["docs", "--all", "--output-dir", tmp_dir])
        assert exit_code == 0
        assert (Path(tmp_dir) / "index.html").exists()
