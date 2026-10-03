"""Catalog discovery is configurable, deterministic and reports collisions (#202, #203)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from omniuart.core.catalog import PROTOCOL_PATH_ENV, SCRIPT_PATH_ENV, CatalogManager


def proto(name: str, baud: int = 9600) -> str:
    return yaml.safe_dump({
        "metadata": {"name": name, "version": "1"},
        "serial_config": {"baudrate": baud},
        "framing": {"type": "delimited"},
        "commands": [],
    })


@pytest.fixture
def dirs(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    return a, b


def test_no_developer_machine_paths_remain() -> None:
    source = Path(CatalogManager.__module__.replace(".", "/") + ".py")
    text = (Path(__file__).resolve().parents[2] / "src" / source).read_text()
    assert "Antigravity" not in text and "uart-interface-schema-kit" not in text


def test_first_directory_wins_and_collision_is_reported(dirs) -> None:
    a, b = dirs
    (a / "dev.yaml").write_text(proto("First", 9600))
    (b / "dev.yaml").write_text(proto("Second", 19200))
    catalog = CatalogManager(protocol_dirs=[a, b], script_dirs=[a])
    assert catalog.list_protocol_files() == [(a / "dev.yaml").resolve()]
    assert catalog.get_protocol("dev").metadata.name == "First"
    (c,) = [c for c in catalog.catalog_summary()["collisions"] if c["reason"] == "same filename"]
    assert c["used"].endswith("a/dev.yaml") and c["shadowed"].endswith("b/dev.yaml") and c["identical"] is False


def test_identical_duplicate_is_flagged_as_identical(dirs) -> None:
    a, b = dirs
    for d in dirs:
        (d / "same.yaml").write_text(proto("Same"))
    catalog = CatalogManager(protocol_dirs=[a, b], script_dirs=[a])
    catalog.list_protocol_files()
    assert catalog.collisions[0]["identical"] is True


def test_order_of_directories_decides_precedence(dirs) -> None:
    a, b = dirs
    (a / "dev.yaml").write_text(proto("InA"))
    (b / "dev.yaml").write_text(proto("InB"))
    assert CatalogManager(protocol_dirs=[b, a], script_dirs=[a]).get_protocol("dev").metadata.name == "InB"


def test_duplicate_protocol_names_in_different_files_are_reported(dirs) -> None:
    a, _ = dirs
    (a / "one.yaml").write_text(proto("Twin"))
    (a / "two.yaml").write_text(proto("Twin"))
    catalog = CatalogManager(protocol_dirs=[a], script_dirs=[a])
    (c,) = catalog.name_collisions()
    assert c["name"] == "twin" and c["used"].endswith("one.yaml") and len(c["shadowed"]) == 1


def test_listing_is_sorted_and_stable(dirs) -> None:
    a, _ = dirs
    for n in ("zeta", "Alpha", "mid"):
        (a / f"{n}.yaml").write_text(proto(n))
    names = [f.name for f in CatalogManager(protocol_dirs=[a], script_dirs=[a]).list_protocol_files()]
    assert names == ["Alpha.yaml", "mid.yaml", "zeta.yaml"]


def test_environment_variable_sets_search_path(dirs, monkeypatch) -> None:
    a, b = dirs
    (a / "x.yaml").write_text(proto("X"))
    (b / "y.yaml").write_text(proto("Y"))
    monkeypatch.setenv(PROTOCOL_PATH_ENV, os.pathsep.join([str(a), str(b)]))
    monkeypatch.setenv(SCRIPT_PATH_ENV, str(a))
    catalog = CatalogManager()
    assert {f.name for f in catalog.list_protocol_files()} == {"x.yaml", "y.yaml"}
    assert catalog.protocol_dirs == [a.resolve(), b.resolve()]


def test_explicit_directories_override_the_environment(dirs, monkeypatch) -> None:
    a, b = dirs
    (a / "x.yaml").write_text(proto("X"))
    (b / "y.yaml").write_text(proto("Y"))
    monkeypatch.setenv(PROTOCOL_PATH_ENV, str(a))
    catalog = CatalogManager(protocol_dirs=[b], script_dirs=[b])
    assert [f.name for f in catalog.list_protocol_files()] == ["y.yaml"]


def test_defaults_work_from_the_repository_root(monkeypatch) -> None:
    monkeypatch.delenv(PROTOCOL_PATH_ENV, raising=False)
    monkeypatch.chdir(Path(__file__).resolve().parents[2])
    summary = CatalogManager().catalog_summary()
    assert summary["protocols_found"] >= 30 and summary["collisions"] == []
