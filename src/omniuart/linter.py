"""Protocol definition linter and schema format converter for OmniUART."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from jsonschema import Draft202012Validator

from omniuart.core.models import ProtocolSpec, load_protocol
from omniuart.utils.resources import get_resource_path


def load_kit_schema() -> Dict[str, Any]:
    """Load uart-interface.schema.json standard JSON Schema."""
    schema_path = get_resource_path("uart-interface-schema-kit/kit/schema/uart-interface.schema.json")
    if not schema_path.exists():
        schema_path = get_resource_path("schemas/protocol.schema.json")
    raw = schema_path.read_text(encoding="utf-8")
    return json.loads(raw)


def lint_protocol_file(file_path: Union[str, Path]) -> Tuple[bool, List[str]]:
    """Lint and validate a YAML/JSON protocol definition file against JSON Schema.
    
    Returns (is_valid, error_messages).
    """
    path = Path(file_path)
    if not path.exists():
        return False, [f"File not found: {path}"]

    try:
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) if path.suffix.lower() in (".yaml", ".yml") else json.loads(raw)
    except Exception as e:
        return False, [f"Syntax / Parsing Error: {e}"]

    # Standard Pydantic model validation check
    errors: List[str] = []
    try:
        load_protocol(path)
    except Exception as e:
        errors.append(f"OmniUART Model Validation: {e}")

    # JSON Schema Draft2020-12 Validation check
    try:
        schema = load_kit_schema()
        validator = Draft202012Validator(schema)
        for err in validator.iter_errors(data):
            path_str = " -> ".join(str(p) for p in err.absolute_path) or "root"
            errors.append(f"Schema Violation at [{path_str}]: {err.message}")
    except Exception as e:
        errors.append(f"Schema Engine Note: {e}")

    is_valid = (len(errors) == 0)
    return is_valid, errors


def convert_protocol_to_kit(
    file_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Convert a legacy OmniUART protocol specification into uart-interface.schema.json kit format."""
    path = Path(file_path)
    spec = load_protocol(path)

    # Transform to kit schema dict structure
    kit_dict: Dict[str, Any] = {
        "title": spec.metadata.name,
        "version": spec.metadata.version,
        "description": spec.metadata.description or f"{spec.metadata.name} protocol definition",
        "physicalLayer": {
            "baudRate": spec.serial_config.baudrate,
            "dataBits": spec.serial_config.bytesize,
            "parity": spec.serial_config.parity,
            "stopBits": spec.serial_config.stopbits,
            "hardwareFlowControl": spec.serial_config.flow_control != "none",
        },
        "framing": {
            "style": "delimiter-framed" if spec.framing.type.value == "delimited" else "binary",
            "preamble": spec.framing.header if isinstance(spec.framing.header, list) else None,
        },
        "commands": [],
    }

    if spec.framing.integrity:
        kit_dict["integrityCheck"] = {
            "algorithm": spec.framing.integrity.algorithm,
            "placement": "trailing",
        }

    for cmd in spec.commands:
        fields = []
        for p in cmd.parameters:
            fields.append({
                "name": p.name,
                "baseType": p.type.value,
                "units": p.unit,
                "byteOrder": p.endian,
            })
        cmd_entry: Dict[str, Any] = {
            "name": cmd.name,
            "description": cmd.description or f"Command {cmd.name}",
            "tags": cmd.tags,
            "fields": fields,
        }
        if cmd.response:
            resp_fields = []
            for rf in cmd.response.fields:
                resp_fields.append({
                    "name": rf.name,
                    "baseType": rf.type.value,
                    "units": rf.unit,
                })
            cmd_entry["response"] = {
                "timeoutMs": cmd.response.timeout_ms,
                "fields": resp_fields,
            }
        kit_dict["commands"].append(cmd_entry)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(kit_dict, indent=2), encoding="utf-8")

    return kit_dict
