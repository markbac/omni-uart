"""Misspelled or unsupported configuration keys are errors, not silently dropped (#201)."""

from __future__ import annotations

import copy

import pytest
import yaml
from pydantic import ValidationError

from omniuart.core.models import load_protocol, load_script

BASE = {
    "metadata": {"name": "T", "version": "1"},
    "serial_config": {"baudrate": 9600},
    "framing": {"type": "delimited"},
    "commands": [{"name": "A", "id": "A", "parameters": [{"name": "x", "type": "uint8"}], "response": {"fields": []}}],
}


def with_typo(path: list, key: str):
    data = copy.deepcopy(BASE)
    node = data
    for part in path:
        node = node[part]
    node[key] = 1
    return data


def write(tmp_path, data):
    p = tmp_path / "p.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_valid_protocol_still_loads(tmp_path) -> None:
    assert load_protocol(write(tmp_path, BASE)).metadata.name == "T"


@pytest.mark.parametrize(
    "path,key",
    [
        ([], "comands"),
        (["metadata"], "autor"),
        (["serial_config"], "baud_rate"),
        (["framing"], "sufix"),
        (["commands", 0], "safty"),
        (["commands", 0, "parameters", 0], "minimum"),
        (["commands", 0, "response"], "timeout"),
    ],
)
def test_typoed_protocol_key_is_rejected(tmp_path, path, key) -> None:
    with pytest.raises(ValidationError, match=key):
        load_protocol(write(tmp_path, with_typo(path, key)))


def test_typoed_script_key_is_rejected(tmp_path) -> None:
    data = {"meta": {"name": "s", "protocol": "p"}, "steps": [{"command": "A", "param": {"x": 1}}]}
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(data))
    with pytest.raises(ValidationError, match="param"):
        load_script(p)
