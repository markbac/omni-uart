"""Unit test for version alignment across package metadata, pyproject.toml, and CLI (#225)."""

import tomllib
from pathlib import Path

import pytest

import omniuart
from omniuart.cli import build_parser


def test_package_version_matches_pyproject_toml():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    assert pyproject_path.exists()

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    pyproject_version = data["project"]["version"]
    assert omniuart.__version__ == pyproject_version
    assert omniuart.__version__ == "2.0.0"


def test_cli_version_flag(capsys):
    parser = build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert omniuart.__version__ in captured.out or omniuart.__version__ in captured.err
