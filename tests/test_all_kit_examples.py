"""Comprehensive validation and execution tests for all schema kit protocol examples and sequences."""

from __future__ import annotations

import pytest
from pathlib import Path
from omniuart.core.catalog import CatalogManager
from omniuart.core.models import load_protocol, load_script
from omniuart.linter import lint_protocol_file


def test_catalog_discovers_all_kit_examples() -> None:
    catalog = CatalogManager()
    summary = catalog.catalog_summary()
    
    # Verify at least 32 protocols and 3 scripts are discovered
    assert summary["protocols_found"] >= 32
    assert summary["scripts_found"] >= 3


def test_lint_all_kit_protocol_files() -> None:
    proto_dir = Path("examples/protocols")
    assert proto_dir.exists()

    for p_file in proto_dir.glob("*.*"):
        if p_file.suffix in [".json", ".yaml", ".yml"]:
            is_valid, errors = lint_protocol_file(p_file)
            assert is_valid, f"Protocol file {p_file.name} failed linting: {errors}"


def test_load_all_kit_protocols_and_scripts() -> None:
    catalog = CatalogManager()
    summary = catalog.catalog_summary()
    
    for p_summary in summary["protocols"]:
        spec = catalog.get_protocol(p_summary["filename"])
        assert spec is not None
        assert spec.metadata.name
        assert spec.commands

    for s_summary in summary["scripts"]:
        script = catalog.get_script(s_summary["filename"])
        assert script is not None
        assert script.meta.name or s_summary["name"]
        assert script.steps
