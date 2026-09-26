"""AsyncAPI Specification Exporter & Generator for OmniUART Protocols.

Converts OmniUART ProtocolSpec instances into valid AsyncAPI 2.6.0 specification documents.
"""

from __future__ import annotations

import json
from typing import Any, Dict
import yaml

from omniuart.core.models import ProtocolSpec, load_protocol


def export_asyncapi_dict(spec: ProtocolSpec) -> Dict[str, Any]:
    """Convert ProtocolSpec into AsyncAPI 2.6.0 schema structure."""
    meta = spec.metadata
    bytesize = getattr(spec.serial_config, "bytesize", 8)
    stopbits = getattr(spec.serial_config, "stopbits", 1.0)
    parity = getattr(spec.serial_config, "parity", "none")
    integrity_alg = spec.framing.integrity.algorithm if spec.framing.integrity else "none"

    asyncapi_doc: Dict[str, Any] = {
        "asyncapi": "2.6.0",
        "info": {
            "title": meta.name,
            "version": meta.version,
            "description": meta.description or f"Hardware UART Protocol Specification for {meta.name}",
            "contact": {
                "name": meta.author or "Mark Bacon",
            },
        },
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
                }
            }
        },
        "channels": {},
        "components": {
            "messages": {},
            "schemas": {},
        }
    }

    # Build channels and messages for commands and responses
    for cmd in spec.commands:
        cmd_id_str = f"0x{cmd.id:02X}" if isinstance(cmd.id, int) else str(cmd.id)
        channel_name = f"omniuart/cmd/{cmd.name}"
        
        # Publish operation (Client -> MCU)
        cmd_schema_properties: Dict[str, Any] = {
            "command_id": {"type": "integer", "const": cmd.id, "description": f"Opcode ID for {cmd.name}"}
        }

        if cmd.parameters:
            for param in cmd.parameters:
                param_type = "number" if param.type.value in ["float32", "float64"] else "integer"
                param_dict: Dict[str, Any] = {"type": param_type}
                if param.unit:
                    param_dict["unit"] = param.unit
                if param.min is not None:
                    param_dict["minimum"] = param.min
                if param.max is not None:
                    param_dict["maximum"] = param.max
                cmd_schema_properties[param.name] = param_dict

        asyncapi_doc["components"]["schemas"][f"{cmd.name}_Request"] = {
            "type": "object",
            "properties": cmd_schema_properties,
            "description": cmd.description or f"Command payload for {cmd.name}",
        }

        asyncapi_doc["channels"][channel_name] = {
            "publish": {
                "summary": f"Send command {cmd.name} (ID: {cmd_id_str})",
                "description": cmd.description or f"Dispatch {cmd.name} frame to microcontroller over serial line",
                "message": {
                    "name": f"{cmd.name}_Message",
                    "title": f"{cmd.name} Command",
                    "payload": {"$ref": f"#/components/schemas/{cmd.name}_Request"},
                }
            }
        }

        # Response operation (MCU -> Client) if response defined
        if cmd.response:
            resp_channel_name = f"omniuart/resp/{cmd.name}"
            resp_schema_properties: Dict[str, Any] = {}
            for rf in cmd.response.fields:
                rf_type = "number" if rf.type.value in ["float32", "float64"] else "integer"
                rf_dict: Dict[str, Any] = {"type": rf_type}
                if rf.unit:
                    rf_dict["unit"] = rf.unit
                resp_schema_properties[rf.name] = rf_dict

            asyncapi_doc["components"]["schemas"][f"{cmd.name}_Response"] = {
                "type": "object",
                "properties": resp_schema_properties,
                "description": f"Decoded response frame payload for {cmd.name}",
            }

            asyncapi_doc["channels"][resp_channel_name] = {
                "subscribe": {
                    "summary": f"Receive response for {cmd.name}",
                    "description": f"Decoded async payload stream from device after command {cmd.name}",
                    "message": {
                        "name": f"{cmd.name}_Response_Message",
                        "title": f"{cmd.name} Response",
                        "payload": {"$ref": f"#/components/schemas/{cmd.name}_Response"},
                    }
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
