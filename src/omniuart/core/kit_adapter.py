"""Adapter for parsing uart-interface-schema-kit protocols into OmniUART ProtocolSpec instances."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from omniuart.core.models import (
    CommandIdSpec,
    CommandSpec,
    FieldSpec,
    FieldType,
    FramingConfig,
    FramingType,
    IntegritySpec,
    LengthSpec,
    ProtocolMeta,
    ProtocolSpec,
    ResponseSpec,
    SerialConfig,
    TelemetrySpec,
)

EXCLUDED_PROTOCOLS = {"g460", "g460-uart-interface", "g460-uart-interface.json"}


def _map_field_type(base_type: str, size_bytes: Optional[int] = None) -> FieldType:
    """Map generic schema base type and size to OmniUART FieldType."""
    base = (base_type or "uint").lower()
    if base in ("uint", "integer", "unsigned"):
        if size_bytes == 1:
            return FieldType.UINT8
        elif size_bytes == 2:
            return FieldType.UINT16
        elif size_bytes == 4:
            return FieldType.UINT32
        elif size_bytes == 8:
            return FieldType.UINT64
        return FieldType.UINT16
    elif base in ("int", "signed"):
        if size_bytes == 1:
            return FieldType.INT8
        elif size_bytes == 2:
            return FieldType.INT16
        elif size_bytes == 4:
            return FieldType.INT32
        elif size_bytes == 8:
            return FieldType.INT64
        return FieldType.INT16
    elif base in ("float", "double"):
        if size_bytes == 8:
            return FieldType.FLOAT64
        return FieldType.FLOAT32
    elif base in ("bool", "boolean"):
        return FieldType.BOOL
    elif base in ("enum", "choice"):
        return FieldType.ENUM
    elif base in ("ascii", "utf8", "text", "string"):
        return FieldType.STRING
    elif base in ("raw", "bytes", "binary", "hex"):
        return FieldType.BYTES
    return FieldType.BYTES


def _map_algorithm_name(algo: str) -> str:
    """Map kit schema integrity algorithm to OmniUART algorithm string."""
    algo_clean = algo.lower().replace("-", "_").replace(" ", "_")
    mappings = {
        "crc_16_modbus": "crc16_modbus",
        "crc_16_ccitt": "crc16_ccitt",
        "crc_32": "crc32",
        "sum_8": "sum8",
        "xor_8": "xor8",
        "crc_8": "crc8",
    }
    return mappings.get(algo_clean, algo_clean)


def parse_kit_protocol(data: Dict[str, Any], source_name: Optional[str] = None) -> ProtocolSpec:
    """Parse a uart-interface-schema-kit dictionary into an OmniUART ProtocolSpec.
    
    Explicitly excludes G460 protocol definitions as per configuration rules.
    """
    title = data.get("title") or data.get("name") or "Unnamed Protocol"
    version = str(data.get("version") or "1.0.0")
    description = data.get("description")

    # Guard: check if source or title is G460
    check_name = (source_name or "").lower()
    title_lower = title.lower()
    if "g460" in check_name or "g460" in title_lower:
        raise ValueError("G460 protocol is explicitly excluded from processing")

    # Extract metadata
    metadata = ProtocolMeta(
        name=title,
        version=version,
        description=description,
        author=data.get("author"),
    )

    # Extract serial physical layer config
    phys = data.get("physicalLayer", {})
    baud = phys.get("baudRate", 115200)
    if isinstance(baud, list):
        # Pick a standard baudrate from the list or default to 115200
        valid_bauds = [b for b in baud if b in {9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600}]
        baudrate = valid_bauds[0] if valid_bauds else 115200
    elif isinstance(baud, int) and baud in {9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600}:
        baudrate = baud
    else:
        baudrate = 115200

    bytesize = phys.get("dataBits", 8)
    parity_val = str(phys.get("parity", "none")).lower()
    parity = parity_val if parity_val in ("none", "even", "odd", "mark", "space") else "none"
    stopbits = float(phys.get("stopBits", 1))

    flow_ctrl = phys.get("hardwareFlowControl", "none")
    flow_str = "hardware" if flow_ctrl in (True, "rts-cts") else "none"

    serial_config = SerialConfig(
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        flow_control=flow_str,
    )

    # Extract framing config
    framing_raw = data.get("framing", {})
    style = framing_raw.get("style", "binary")
    framing_type = FramingType.DELIMITED if style in ("delimiter-framed", "silence-delimited", "scpi-delimited") else FramingType.BINARY

    header_bytes = None
    if "preamble" in framing_raw:
        pre = framing_raw["preamble"]
        if isinstance(pre, list):
            header_bytes = pre
        elif isinstance(pre, str) and pre.startswith("0x"):
            header_bytes = [int(pre, 16)]
    elif "startDelimiter" in framing_raw:
        start_d = framing_raw["startDelimiter"]
        if isinstance(start_d, list):
            header_bytes = start_d
        elif isinstance(start_d, str):
            header_bytes = [ord(c) for c in start_d]

    footer_bytes = None
    if "endDelimiter" in framing_raw:
        end_d = framing_raw["endDelimiter"]
        if isinstance(end_d, list):
            footer_bytes = end_d
        elif isinstance(end_d, str):
            footer_bytes = [ord(c) for c in end_d]

    integrity_raw = data.get("integrityCheck", {})
    integrity_spec = None
    if integrity_raw and "algorithm" in integrity_raw:
        algo = _map_algorithm_name(integrity_raw["algorithm"])
        custom_params = integrity_raw.get("customParameters", {})
        integrity_spec = IntegritySpec(
            algorithm=algo,
            width=custom_params.get("width"),
            poly=custom_params.get("poly"),
            init=custom_params.get("init"),
            refin=custom_params.get("refin", False),
            refout=custom_params.get("refout", False),
            xorout=custom_params.get("xorout", 0),
            endian=custom_params.get("endian", "little"),
        )

    framing_config = FramingConfig(
        type=framing_type,
        header=header_bytes,
        integrity=integrity_spec,
        footer=footer_bytes,
        delimiter=framing_raw.get("startDelimiter") if isinstance(framing_raw.get("startDelimiter"), str) else None,
    )

    # Extract field definitions map
    field_types = data.get("fieldTypes", {})

    def resolve_field_type(field_def: Dict[str, Any]) -> FieldSpec:
        name = field_def.get("name", "unnamed")
        type_ref = field_def.get("type", "")
        type_info = field_types.get(type_ref, {}) if type_ref in field_types else {}
        base_type = type_info.get("baseType") or field_def.get("baseType") or "bytes"
        size_bytes = type_info.get("sizeBytes") or field_def.get("sizeBytes")
        
        ftype = _map_field_type(base_type, size_bytes)
        endian = field_def.get("byteOrder") or type_info.get("byteOrder") or data.get("encoding", {}).get("byteOrder", "little")
        endian_str = "big" if "big" in str(endian).lower() else "little"

        options_dict = None
        if "enumValues" in type_info:
            options_dict = type_info["enumValues"]
        elif "enumValues" in field_def:
            options_dict = field_def["enumValues"]

        return FieldSpec(
            name=name,
            type=ftype,
            endian=endian_str,
            unit=field_def.get("units") or type_info.get("units"),
            options=options_dict,
        )

    # Extract commands
    commands: List[CommandSpec] = []
    raw_commands = data.get("commands", [])
    for idx, cmd_data in enumerate(raw_commands):
        cmd_name = cmd_data.get("name", f"command_{idx}")
        cmd_id: Union[int, str] = idx
        params: List[FieldSpec] = []

        fields = cmd_data.get("fields", [])
        for f in fields:
            field_spec = resolve_field_type(f)
            if f.get("role") == "discriminator" or "constValue" in f:
                cmd_id = f.get("constValue", cmd_id)
            params.append(field_spec)

        response_spec = None
        if "response" in cmd_data:
            resp_data = cmd_data["response"]
            resp_fields = [resolve_field_type(rf) for rf in resp_data.get("fields", [])]
            response_spec = ResponseSpec(
                id=resp_data.get("id"),
                timeout_ms=resp_data.get("timeoutMs", 1000),
                fields=resp_fields,
            )

        tags = list(cmd_data.get("tags", []))
        cmd_name_lower = cmd_name.lower()
        if not tags and any(kw in cmd_name_lower for kw in ("version", "status", "info", "read", "get", "poll")):
            tags.append("dashboard")

        commands.append(
            CommandSpec(
                name=cmd_name,
                id=cmd_id,
                description=cmd_data.get("description"),
                tags=tags,
                parameters=params,
                response=response_spec,
            )
        )

    if not commands:
        # Fallback dummy command if kit specification defined high-level messages without commands list
        commands.append(CommandSpec(name="ping", id=1))

    return ProtocolSpec(
        schema_version="1.0.0",
        metadata=metadata,
        serial_config=serial_config,
        framing=framing_config,
        commands=commands,
    )


def load_kit_protocol(source: Union[str, Path, Dict[str, Any]]) -> ProtocolSpec:
    """Load a protocol definition from file path or dictionary conforming to uart-interface.schema.json."""
    if isinstance(source, dict):
        return parse_kit_protocol(source)
    path = Path(source)
    source_name = path.name
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    return parse_kit_protocol(data, source_name=source_name)
