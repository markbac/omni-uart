"""The committed JSON Schemas are generated from the Pydantic models and must not drift (#200)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from omniuart.schema_export import build_protocol_schema, build_script_schema, default_schema_dir, render

ROOT = Path(__file__).resolve().parents[2]
NATIVE_PROTOCOLS = ["ascii_device.yaml", "binary_sensor_node.yaml", "custom_crc_device.yaml", "smart_actuator.json"]


def load(path: Path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text) if path.suffix in (".yaml", ".yml") else json.loads(text)


@pytest.mark.parametrize("name,builder", [("protocol.schema.json", build_protocol_schema), ("script.schema.json", build_script_schema)])
def test_committed_schema_matches_models(name, builder) -> None:
    committed = (default_schema_dir() / name).read_text(encoding="utf-8")
    assert committed == render(builder()), "run: python -m omniuart.schema_export"


def test_generated_schemas_are_valid_json_schema() -> None:
    Draft202012Validator.check_schema(build_protocol_schema())
    Draft202012Validator.check_schema(build_script_schema())


@pytest.mark.parametrize("name", NATIVE_PROTOCOLS)
def test_native_examples_validate_against_generated_schema(name) -> None:
    errors = list(Draft202012Validator(build_protocol_schema()).iter_errors(load(ROOT / "examples" / "protocols" / name)))
    assert not errors, [e.message for e in errors]


def test_native_example_scripts_validate_against_generated_schema() -> None:
    validator = Draft202012Validator(build_script_schema())
    scripts = [p for p in (ROOT / "examples" / "scripts").glob("*.*") if p.suffix in (".yaml", ".yml", ".json")]
    native = [(p, load(p)) for p in scripts]
    native = [(p, d) for p, d in native if "meta" in d]  # kit sequences use another format (sequence adapter)
    assert len(native) >= 2
    for path, data in native:
        errors = list(validator.iter_errors(data))
        assert not errors, (path.name, [e.message for e in errors])


def test_schema_rejects_unknown_keys_like_the_models() -> None:
    data = load(ROOT / "examples" / "protocols" / "ascii_device.yaml")
    data["comands"] = []
    messages = [e.message for e in Draft202012Validator(build_protocol_schema()).iter_errors(data)]
    assert any("comands" in m for m in messages)
