"""Generate the native JSON Schemas from the Pydantic models, which are the canonical definition.

Run ``python -m omniuart.schema_export`` to rewrite ``schemas/protocol.schema.json`` and
``schemas/script.schema.json``. A test fails if the committed files differ from the generated ones.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Type

from pydantic import BaseModel

from omniuart.core.models import ProtocolSpec, ScriptSpec

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"


def build_schema(model: Type[BaseModel], title: str) -> Dict[str, Any]:
    """JSON Schema (draft 2020-12) of ``model`` as it validates input."""
    schema = model.model_json_schema(mode="validation")
    return {"$schema": SCHEMA_DIALECT, **schema, "title": title}


def build_protocol_schema() -> Dict[str, Any]:
    return build_schema(ProtocolSpec, "OmniUART Protocol Specification Schema")


def build_script_schema() -> Dict[str, Any]:
    return build_schema(ScriptSpec, "OmniUART Automation Script Schema")


def build_asyncapi_extension_schema() -> Dict[str, Any]:
    """JSON Schema of the ``x-omniuart`` AsyncAPI extensions (#346), built from the protocol models.

    ``$defs/document`` is the extension on the AsyncAPI document, ``$defs/message`` the one on each
    message and ``$defs/field`` the one on each payload property.
    """
    from omniuart.core.asyncapi_importer import EXTENSION_VERSION

    protocol = ProtocolSpec.model_json_schema(mode="validation", ref_template="#/$defs/{model}")
    defs: Dict[str, Any] = dict(protocol.get("$defs", {}))
    props = protocol["properties"]
    document_props: Dict[str, Any] = {
        "version": {"type": "string", "description": f"Extension vocabulary version ({EXTENSION_VERSION})"},
        "schema_version": props["schema_version"],
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"description": {"type": "string"}, "author": {"type": "string"}},
            "description": "Metadata AsyncAPI info does not hold exactly (info.title and info.version give name and version)",
        },
        "serial": {"$ref": "#/$defs/SerialConfig"},
        "framing": {"$ref": "#/$defs/FramingConfig"},
    }
    for name, schema in props.items():
        if name not in ("metadata", "commands", "telemetry", "serial_config", "framing", "schema_version"):
            document_props[name] = schema
    field = dict(defs["FieldSpec"])
    field_props = {k: v for k, v in field["properties"].items() if k not in ("name", "nested_fields")}
    field_props["options"] = {
        "type": "array",
        "items": {"type": "object", "required": ["value", "label"], "properties": {"value": {"type": ["integer", "string"]}, "label": {"type": "string"}}},
        "description": "Enumeration values and labels (a list, so integer values stay integers in JSON)",
    }
    field_props["role"] = {"const": "command_id", "description": "Marks the informative command id property, which the importer skips"}
    command = defs["CommandSpec"]["properties"]
    response = defs["ResponseSpec"]["properties"]
    message = {
        "type": "object",
        "additionalProperties": False,
        "required": ["kind"],
        "properties": {
            "kind": {"enum": ["command", "response", "telemetry"]},
            "name": {"type": "string", "description": "Command or telemetry name (default: the message name)"},
            "id": {"anyOf": [{"type": "integer"}, {"type": "string"}], "description": "Message id on the wire; for a response, the response id"},
            "description": {"type": "string"},
            "safety": command["safety"],
            "safety_reason": command["safety_reason"],
            "tags": command["tags"],
            "correlate": command["correlate"],
            "command": {"type": "string", "description": "Response only: the command this message answers"},
            "timeout_ms": response["timeout_ms"],
            "success_pattern": response["success_pattern"],
            "error_patterns": response["error_patterns"],
        },
    }
    defs["document"] = {"type": "object", "additionalProperties": False, "required": ["framing"], "properties": document_props}
    defs["message"] = message
    defs["field"] = {"type": "object", "additionalProperties": False, "properties": field_props}
    return {
        "$schema": SCHEMA_DIALECT,
        "title": "OmniUART AsyncAPI Extensions (x-omniuart)",
        "description": "Extensions that make an AsyncAPI document a complete OmniUART protocol source",
        "$ref": "#/$defs/document",
        "$defs": defs,
    }


def render(schema: Dict[str, Any]) -> str:
    return json.dumps(schema, indent=2) + "\n"


def default_schema_dir() -> Path:
    from omniuart.utils.resources import get_resource_path
    schema_dir = get_resource_path("schemas")
    if schema_dir.is_dir():
        return schema_dir
    return Path(__file__).resolve().parents[2] / "schemas"


def main() -> int:
    out = default_schema_dir()
    (out / "protocol.schema.json").write_text(render(build_protocol_schema()), encoding="utf-8")
    (out / "script.schema.json").write_text(render(build_script_schema()), encoding="utf-8")
    (out / "x-omniuart.schema.json").write_text(render(build_asyncapi_extension_schema()), encoding="utf-8")
    print(f"Wrote protocol.schema.json, script.schema.json and x-omniuart.schema.json to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
