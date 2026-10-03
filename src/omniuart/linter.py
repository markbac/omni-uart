"""Protocol definition linter and schema format converter for OmniUART."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml
from jsonschema import Draft202012Validator

from omniuart.core.models import ProtocolSpec, load_protocol
from omniuart.utils.resources import get_resource_path


def load_kit_schema(is_kit_format: bool = False) -> Dict[str, Any]:
    """Load JSON Schema (uart-interface.schema.json or protocol.schema.json)."""
    if is_kit_format:
        schema_path = get_resource_path("schemas/uart-interface.schema.json")
        if not schema_path.exists():
            schema_path = get_resource_path("uart-interface-schema-kit/kit/schema/uart-interface.schema.json")
    else:
        schema_path = get_resource_path("schemas/protocol.schema.json")

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

    # Detect kit format vs native format
    is_kit_format = bool(
        isinstance(data, dict) and ("title" in data or "physicalLayer" in data or "info" in data or "$schema" in data)
    )

    # JSON Schema Draft2020-12 Validation check
    try:
        schema = load_kit_schema(is_kit_format=is_kit_format)
        validator = Draft202012Validator(schema)
        for err in validator.iter_errors(data):
            path_str = " -> ".join(str(p) for p in err.absolute_path) or "root"
            errors.append(f"Schema Violation at [{path_str}]: {err.message}")
    except Exception as e:
        errors.append(f"Schema Engine Note: {e}")

    is_valid = (len(errors) == 0)
    return is_valid, errors


_BASE_TYPES = {
    "uint8": ("uint", 1), "uint16": ("uint", 2), "uint32": ("uint", 4), "uint64": ("uint", 8),
    "int8": ("int", 1), "int16": ("int", 2), "int32": ("int", 4), "int64": ("int", 8),
    "float32": ("float", 4), "float64": ("float", 8),
    "bool": ("bool", None), "enum": ("enum", None), "string": ("string", None), "bytes": ("bytes", None),
}


class ConversionLossError(Exception):
    """Raised when a conversion cannot preserve everything; ``losses`` lists what would be lost."""

    def __init__(self, losses: List[str], kit: Dict[str, Any]) -> None:
        super().__init__(f"conversion would lose {len(losses)} value(s)")
        self.losses = losses
        self.kit = kit


def _kit_field(f: Any) -> Dict[str, Any]:
    base, size = _BASE_TYPES[f.type.value]
    out: Dict[str, Any] = {"name": f.name, "type": base}
    size = f.length if f.length is not None and base in ("string", "bytes") else size
    if size is not None:
        out["sizeBytes"] = size
    out["byteOrder"] = "big-endian" if f.endian == "big" else "little-endian"
    if f.unit:
        out["units"] = f.unit
    ext = {k: v for k, v in (("min", f.min), ("max", f.max), ("scale", f.scale), ("default", f.default)) if v is not None}
    if ext:
        out["x-omniuart"] = ext  # not expressible in the kit schema; read back by OmniUART
    if f.options:
        out["enumValues"] = {str(k): v for k, v in f.options.items()}
    return out


def _kit_message(msg_id: Any, fields: List[Any], delimited: bool) -> List[Dict[str, Any]]:
    disc: Dict[str, Any] = {"name": "id", "role": "discriminator", "constValue": msg_id}
    if isinstance(msg_id, int) and not delimited:
        disc.update(type="uint", sizeBytes=1)
    else:
        disc["type"] = "string"
    return [disc] + [_kit_field(f) for f in fields]


def _kit_integrity(spec: Any) -> Dict[str, Any]:
    from omniuart.core.kit_adapter import _COVERAGE, _TRANSFORMS

    ic = spec.framing.integrity
    out: Dict[str, Any] = {"algorithm": ic.algorithm, "placement": "trailing"}
    if ic.algorithm == "custom":
        out["customParameters"] = {
            k: v for k, v in {
                "widthBits": ic.width, "polynomial": ic.poly, "initialValue": ic.init, "reflectInput": ic.refin,
                "reflectOutput": ic.refout, "finalXor": ic.xorout, "check": ic.check, "endian": ic.endian,
            }.items() if v is not None
        }
    inv_cov = {v: k for k, v in _COVERAGE.items()}
    inv_tr = {v: k for k, v in _TRANSFORMS.items()}
    if ic.covers in inv_cov and ic.covers != "after_header":
        out["coverage"] = inv_cov[ic.covers]
    if ic.transform in inv_tr:
        out["finalTransform"] = inv_tr[ic.transform]
    if ic.carry_wrap:
        out["summationMode"] = "carry-wrapped"
    return out


def _flatten(value: Any, prefix: str = "") -> Dict[str, Any]:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
        return out
    if isinstance(value, list):
        out = {f"{prefix}.length": len(value)}
        for i, v in enumerate(value):
            out.update(_flatten(v, f"{prefix}[{i}]"))
        return out
    return {prefix: value}


def find_conversion_losses(original: ProtocolSpec, kit: Dict[str, Any]) -> List[str]:
    """Reload ``kit`` and list every value that differs from ``original`` (empty when the round trip is exact)."""
    from omniuart.core.kit_adapter import parse_kit_protocol

    try:
        reloaded = parse_kit_protocol(kit)
    except Exception as exc:  # noqa: BLE001 - an unloadable result loses everything
        return [f"the converted protocol cannot be loaded back: {exc}"]
    def dump(spec: ProtocolSpec) -> Dict[str, Any]:
        data = spec.model_dump(mode="json")
        integrity = data["framing"].get("integrity")
        if integrity is not None and integrity.get("algorithm") == "none":
            data["framing"]["integrity"] = None  # "no integrity check" and "no block" mean the same
        return data

    before = _flatten(dump(original))
    after = _flatten(dump(reloaded))
    losses = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            losses.append(f"{key}: {before.get(key)!r} -> {after.get(key)!r}")
    return losses


def convert_protocol_to_kit(
    file_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    lossy: bool = False,
) -> Dict[str, Any]:
    """Convert an OmniUART protocol into the uart-interface.schema.json kit format.

    The result is reloaded and compared with the original. If anything would be lost (the kit schema
    cannot express every native setting) :class:`ConversionLossError` is raised and nothing is written,
    unless ``lossy`` is true.
    """
    spec = load_protocol(Path(file_path))
    delimited = spec.framing.type.value == "delimited"

    kit_dict: Dict[str, Any] = {
        "title": spec.metadata.name,
        "version": spec.metadata.version,
        "physicalLayer": {
            "baudRate": spec.serial_config.baudrate,
            "dataBits": spec.serial_config.bytesize,
            "parity": spec.serial_config.parity,
            "stopBits": spec.serial_config.stopbits,
            "hardwareFlowControl": spec.serial_config.flow_control != "none",
        },
        "framing": {"style": "delimiter-framed" if delimited else "sync-length-payload-crc"},
        "commands": [],
    }
    if spec.metadata.description:
        kit_dict["description"] = spec.metadata.description
    if spec.metadata.author:
        kit_dict["author"] = spec.metadata.author
    if isinstance(spec.framing.header, list):
        kit_dict["framing"]["preamble"] = spec.framing.header
    if isinstance(spec.framing.footer, list):
        kit_dict["framing"]["endDelimiter"] = spec.framing.footer
    if spec.framing.integrity and spec.framing.integrity.algorithm != "none":
        kit_dict["integrityCheck"] = _kit_integrity(spec)

    for cmd in spec.commands:
        entry: Dict[str, Any] = {
            "name": cmd.name,
            "tags": cmd.tags,
            "fields": _kit_message(cmd.id, cmd.parameters, delimited),
        }
        if cmd.description:
            entry["description"] = cmd.description
        if cmd.safety.value != "mutating":
            entry["x-omniuart"] = {"safety": cmd.safety.value}
        if cmd.response:
            entry["response"] = {
                "id": cmd.response.id,
                "timeoutMs": cmd.response.timeout_ms,
                "fields": [_kit_field(f) for f in cmd.response.fields],
            }
        kit_dict["commands"].append(entry)
    if spec.telemetry:
        kit_dict["responses"] = [
            {"name": t.name, "description": t.description or t.name, "tags": t.tags, "fields": _kit_message(t.id, t.fields, delimited)}
            for t in spec.telemetry
        ]

    losses = find_conversion_losses(spec, kit_dict)
    if losses and not lossy:
        raise ConversionLossError(losses, kit_dict)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(kit_dict, indent=2), encoding="utf-8")

    return kit_dict
