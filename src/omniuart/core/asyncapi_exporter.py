"""AsyncAPI Specification Exporter & Generator for OmniUART Protocols.

Converts OmniUART ProtocolSpec instances into valid AsyncAPI 2.6.0 specification documents.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict
import yaml

from omniuart.core.models import FieldSpec, ProtocolSpec


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
        schema = {"type": "string", "contentEncoding": "base64"}
    elif val_lower == "enum":
        schema = {"type": "string"}
        if field.options:
            schema["enum"] = list(field.options.keys())
    else:
        schema = {"type": "integer"}

    if field.unit:
        schema["unit"] = field.unit
    if field.min is not None:
        schema["minimum"] = field.min
    if field.max is not None:
        schema["maximum"] = field.max
    if field.default is not None:
        schema["default"] = field.default
    if field.scale is not None and field.scale != 1.0:
        schema["multipleOf"] = field.scale
    if field.options and "enum" not in schema:
        schema["enum"] = list(field.options.keys())

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
            "command_id": {"type": "integer", "const": cmd.id, "description": f"Opcode ID for {cmd.name}"}
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
                    "payload": {"$ref": f"#/components/schemas/{safe_cmd_name}_Request"},
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
                        "payload": {"$ref": f"#/components/schemas/{safe_tel_name}_Telemetry"},
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
