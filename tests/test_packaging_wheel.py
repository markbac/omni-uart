"""Tests for wheel package contents and resource resolution (#336)."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

from omniuart.core.catalog import CatalogManager
from omniuart.linter import load_kit_schema
from omniuart.utils.resources import get_resource_path


def test_resource_resolution_in_development() -> None:
    """Verify get_resource_path locates schemas, examples, and docs."""
    schemas_dir = get_resource_path("schemas")
    assert schemas_dir.exists() and schemas_dir.is_dir()
    assert (schemas_dir / "protocol.schema.json").exists()

    examples_dir = get_resource_path("examples/protocols")
    assert examples_dir.exists() and examples_dir.is_dir()

    docs_dir = get_resource_path("docs")
    assert docs_dir.exists() and docs_dir.is_dir()


def test_load_kit_schema_loads_valid_json() -> None:
    """Verify load_kit_schema resolves protocol and interface schemas."""
    proto_schema = load_kit_schema(is_kit_format=False)
    assert isinstance(proto_schema, dict)
    assert "properties" in proto_schema or "title" in proto_schema or "$schema" in proto_schema

    kit_schema = load_kit_schema(is_kit_format=True)
    assert isinstance(kit_schema, dict)


def test_catalog_manager_discovers_packaged_protocols() -> None:
    """Verify CatalogManager locates protocols and scripts."""
    catalog = CatalogManager()
    protocols = catalog.list_protocol_files()
    assert len(protocols) > 0
    assert any("binary_sensor_node" in str(p) for p in protocols)

    scripts = catalog.list_script_files()
    assert len(scripts) > 0


def test_wheel_build_contains_bundled_assets(tmp_path: Path) -> None:
    """Verify built wheel contains schemas, examples, and docs."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist_dir)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"build --wheel failed: {result.stderr}\n{result.stdout}"

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, "Expected exactly 1 built wheel"
    wheel_file = wheels[0]

    with zipfile.ZipFile(wheel_file, "r") as zf:
        namelist = zf.namelist()

        # Check Python package files
        assert any(n.startswith("omniuart/") and n.endswith("__init__.py") for n in namelist)

        # Check schemas bundled in wheel
        schema_entries = [n for n in namelist if n.startswith("omniuart/schemas/")]
        assert len(schema_entries) > 0, "No schemas found in wheel"
        assert "omniuart/schemas/protocol.schema.json" in namelist
        assert "omniuart/schemas/script.schema.json" in namelist

        # Check examples bundled in wheel
        example_entries = [n for n in namelist if n.startswith("omniuart/examples/")]
        assert len(example_entries) > 0, "No examples found in wheel"

        # Check docs bundled in wheel
        docs_entries = [n for n in namelist if n.startswith("omniuart/docs/")]
        assert len(docs_entries) > 0, "No docs found in wheel"
