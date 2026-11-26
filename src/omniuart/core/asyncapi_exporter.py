"""AsyncAPI Specification Exporter & Generator for OmniUART Protocols.

Converts OmniUART ProtocolSpec instances into valid AsyncAPI 2.6.0 specification documents. The
document carries ``x-omniuart`` extensions (on the document, each message and each payload property)
with everything the wire format needs, so an exported document is a usable protocol source for
:mod:`omniuart.core.asyncapi_importer` (#346).
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List
import yaml

from omniuart.core.models import CommandSpec, FieldSpec, ProtocolSpec, TelemetrySpec

EXTENSION = "x-omniuart"
EXTENSION_VERSION = "1.0"
_TOP_NATIVE = {"metadata", "commands", "telemetry", "serial_config", "framing", "schema_version"}


def field_extension(field: FieldSpec) -> Dict[str, Any]:
    """Every wire attribute of a field except its name and nested fields (those are JSON Schema properties)."""
    ext = field.model_dump(mode="json", exclude={"name", "nested_fields"}, exclude_defaults=True)
    ext["type"] = field.type.value  # always explicit, even when it is a default
    if field.options is not None:
        # A list keeps integer option values integers in JSON, where object keys are always strings.
        ext["options"] = [{"value": k, "label": v} for k, v in field.options.items()]
    return ext


def document_extension(spec: ProtocolSpec) -> Dict[str, Any]:
    """The protocol-level settings AsyncAPI has no place for: serial link, framing, error replies and the rest."""
    ext: Dict[str, Any] = {"version": EXTENSION_VERSION, "schema_version": spec.schema_version}
    meta: Dict[str, Any] = {}
    if spec.metadata.description is not None:
        meta["description"] = spec.metadata.description
    if spec.metadata.author is not None:
        meta["author"] = spec.metadata.author
    if meta:
        ext["metadata"] = meta
    ext["serial"] = spec.serial_config.model_dump(mode="json", exclude_defaults=True)
    ext["serial"]["baudrate"] = spec.serial_config.baudrate
    ext["framing"] = spec.framing.model_dump(mode="json", exclude_none=True)
    for name in type(spec).model_fields:
        if name in _TOP_NATIVE:
            continue
        value = getattr(spec, name)
        if value:
            ext[name] = spec.model_dump(mode="json", include={name}, exclude_defaults=True).get(name, value)
    return ext


def command_extension(cmd: CommandSpec) -> Dict[str, Any]:
    ext: Dict[str, Any] = {"kind": "command", "name": cmd.name, "id": cmd.id, "safety": cmd.safety.value}
    for key in ("safety_reason", "tags", "correlate"):
        value = getattr(cmd, key)
        if value:
            ext[key] = value
    return ext


def response_extension(cmd: CommandSpec) -> Dict[str, Any]:
    assert cmd.response is not None
    ext: Dict[str, Any] = {"kind": "response", "command": cmd.name, "timeout_ms": cmd.response.timeout_ms}
    if cmd.response.id is not None:
        ext["id"] = cmd.response.id
    if cmd.response.success_pattern is not None:
        ext["success_pattern"] = cmd.response.success_pattern
    if cmd.response.error_patterns:
        ext["error_patterns"] = list(cmd.response.error_patterns)
    return ext


def telemetry_extension(tel: TelemetrySpec) -> Dict[str, Any]:
    ext: Dict[str, Any] = {"kind": "telemetry", "name": tel.name, "id": tel.id}
    if tel.tags:
        ext["tags"] = list(tel.tags)
    return ext


def _properties(fields: List[FieldSpec]) -> Dict[str, Any]:
    return {f.name: _map_field_schema(f) for f in fields}


def _sanitise_name(name: str) -> str:
    """Sanitise symbol name for valid AsyncAPI channel and component key references."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def _map_field_schema(field: FieldSpec) -> Dict[str, Any]:
    """Map OmniUART FieldSpec to AsyncAPI 2.6.0 property schema."""
    val = field.type.value if hasattr(field.type, "value") else str(field.type)
    val_lower = val.lower()

    if val_lower in ("float32", "float64", "float", "double"):
        schema: Dict[str, Any] = {"type": "number"}
    elif val_lower in ("bool", "boolean"):
        schema = {"type": "boolean"}
    elif val_lower in ("string", "str", "text", "ascii"):
        schema = {"type": "string"}
    elif val_lower in ("bytes", "hex", "raw", "binary"):
        pattern = f"^[0-9a-fA-F]{{{field.length * 2}}}$" if field.length else "^[0-9a-fA-F]*$"
        schema = {"type": "string", "pattern": pattern}
    elif val_lower == "enum":
        schema = {"type": "string"}
        if field.options:
            schema["enum"] = list(field.options.keys())
    else:
        schema = {"type": "integer"}

    if field.unit:
        schema["x-unit"] = field.unit
    if field.min is not None:
        schema["minimum"] = field.min
    if field.max is not None:
        schema["maximum"] = field.max
    if field.default is not None:
        schema["default"] = field.default
    if field.scale is not None and field.scale != 1.0:
        schema["x-scale"] = field.scale
    if field.options and "enum" not in schema:
        schema["enum"] = list(field.options.keys())
    if field.nested_fields:
        nested = {"type": "object", "properties": _properties(field.nested_fields)}
        if field.is_array:
            schema = {"type": "array", "items": nested}
        else:
            schema = nested
        if field.unit:
            schema["x-unit"] = field.unit
    schema[EXTENSION] = field_extension(field)
    return schema


def export_asyncapi_dict(spec: ProtocolSpec) -> Dict[str, Any]:
    """Convert ProtocolSpec into AsyncAPI 2.6.0 schema structure."""
    meta = spec.metadata
    bytesize = getattr(spec.serial_config, "bytesize", 8)
    stopbits = getattr(spec.serial_config, "stopbits", 1.0)
    parity = getattr(spec.serial_config, "parity", "none")
    integrity_alg = spec.framing.integrity.algorithm if spec.framing.integrity else "none"

    info: Dict[str, Any] = {
        "title": meta.name,
        "version": meta.version,
        "description": meta.description or f"Hardware UART Protocol Specification for {meta.name}",
    }
    if meta.author:
        info["contact"] = {"name": meta.author}

    asyncapi_doc: Dict[str, Any] = {
        "asyncapi": "2.6.0",
        "info": info,
        "servers": {
            "serial_link": {
                "url": f"serial://tty/{spec.serial_config.baudrate}",
                "protocol": "serial",
                "description": f"Physical UART Transport ({spec.serial_config.baudrate} bps, {bytesize}N{stopbits})",
                "bindings": {
                    "serial": {
                        "baudRate": spec.serial_config.baudrate,
                        "dataBits": bytesize,
                        "parity": str(parity),
                        "stopBits": stopbits,
                        "framingType": spec.framing.type.value,
                        "integrity": integrity_alg,
                    }
                },
            }
        },
        EXTENSION: document_extension(spec),
        "channels": {},
        "components": {
            "messages": {},
            "schemas": {},
        },
    }

    # Build channels and messages for commands and responses
    for cmd in spec.commands:
        safe_cmd_name = _sanitise_name(cmd.name)
        cmd_id_str = f"0x{cmd.id:02X}" if isinstance(cmd.id, int) else str(cmd.id)
        channel_name = f"omniuart/cmd/{safe_cmd_name}"

        # Publish operation (Client -> MCU)
        cmd_schema_properties: Dict[str, Any] = {
            "command_id": {"type": "integer" if isinstance(cmd.id, int) else "string", "const": cmd.id, "description": f"Opcode ID for {cmd.name}", EXTENSION: {"role": "command_id"}}
        }

        if cmd.parameters:
            for param in cmd.parameters:
                cmd_schema_properties[param.name] = _map_field_schema(param)

        asyncapi_doc["components"]["schemas"][f"{safe_cmd_name}_Request"] = {
            "type": "object",
            "properties": cmd_schema_properties,
            "description": cmd.description or f"Command payload for {cmd.name}",
        }

        asyncapi_doc["channels"][channel_name] = {
            "publish": {
                "summary": f"Send command {cmd.name} (ID: {cmd_id_str})",
                "description": cmd.description or f"Dispatch {cmd.name} frame to microcontroller over serial line",
                "message": {
                    "name": f"{safe_cmd_name}_Message",
                    "title": f"{cmd.name} Command",
                    **({"description": cmd.description} if cmd.description else {}),
                    "payload": {"$ref": f"#/components/schemas/{safe_cmd_name}_Request"},
                    EXTENSION: command_extension(cmd),
                },
            }
        }

        # Response operation (MCU -> Client) if response defined
        if cmd.response:
            resp_channel_name = f"omniuart/resp/{safe_cmd_name}"
            resp_schema_properties: Dict[str, Any] = {}
            for rf in cmd.response.fields:
                resp_schema_properties[rf.name] = _map_field_schema(rf)

            asyncapi_doc["components"]["schemas"][f"{safe_cmd_name}_Response"] = {
                "type": "object",
                "properties": resp_schema_properties,
                "description": f"Decoded response frame payload for {cmd.name}",
            }

            asyncapi_doc["channels"][resp_channel_name] = {
                "subscribe": {
                    "summary": f"Receive response for {cmd.name}",
                    "description": f"Decoded async payload stream from device after command {cmd.name}",
                    "message": {
                        "name": f"{safe_cmd_name}_Response_Message",
                        "title": f"{cmd.name} Response",
                        "payload": {"$ref": f"#/components/schemas/{safe_cmd_name}_Response"},
                        EXTENSION: response_extension(cmd),
                    },
                }
            }

    # Build channels and messages for unsolicited telemetry
    if spec.telemetry:
        for tel in spec.telemetry:
            safe_tel_name = _sanitise_name(tel.name)
            tel_id_str = f"0x{tel.id:02X}" if isinstance(tel.id, int) else str(tel.id)
            tel_channel_name = f"omniuart/telemetry/{safe_tel_name}"

            tel_schema_properties: Dict[str, Any] = {}
            for tf in tel.fields:
                tel_schema_properties[tf.name] = _map_field_schema(tf)

            asyncapi_doc["components"]["schemas"][f"{safe_tel_name}_Telemetry"] = {
                "type": "object",
                "properties": tel_schema_properties,
                "description": tel.description or f"Device-initiated telemetry payload for {tel.name}",
            }

            asyncapi_doc["channels"][tel_channel_name] = {
                "subscribe": {
                    "summary": f"Unsolicited telemetry message {tel.name} (ID: {tel_id_str})",
                    "description": tel.description or f"Unsolicited telemetry message from device: {tel.name}",
                    "message": {
                        "name": f"{safe_tel_name}_Telemetry_Message",
                        "title": f"{tel.name} Telemetry",
                        **({"description": tel.description} if tel.description else {}),
                        "payload": {"$ref": f"#/components/schemas/{safe_tel_name}_Telemetry"},
                        EXTENSION: telemetry_extension(tel),
                    },
                }
            }

    return asyncapi_doc


def export_asyncapi_yaml(spec: ProtocolSpec) -> str:
    """Export AsyncAPI 2.6.0 document as clean YAML string."""
    doc = export_asyncapi_dict(spec)
    return yaml.dump(doc, sort_keys=False, default_flow_style=False)


def export_asyncapi_json(spec: ProtocolSpec) -> str:
    """Export AsyncAPI 2.6.0 document as formatted JSON string."""
    doc = export_asyncapi_dict(spec)
    return json.dumps(doc, indent=2)
