"""Import / Export Tooling for Protocol Definitions (#221).

Provides conversion and migration tooling between OmniUART ProtocolSpec, YAML, JSON Schema,
CSV tabular formats, and Wireshark dissector metadata, including validation and loss reporting.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from omniuart.core.models import (
    CommandSafety,
    CommandSpec,
    FieldSpec,
    FieldType,
    FramingConfig,
    FramingType,
    ProtocolMeta,
    ProtocolSpec,
    ResponseSpec,
    SerialConfig,
)


def export_csv_protocol(spec: ProtocolSpec) -> str:
    """Export protocol commands and parameters to tabular CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "protocol_name",
        "protocol_version",
        "command_name",
        "command_id",
        "command_safety",
        "field_name",
        "field_type",
        "field_length",
        "field_unit",
    ])

    for cmd in spec.commands:
        if not cmd.parameters:
            writer.writerow([
                spec.metadata.name,
                spec.metadata.version,
                cmd.name,
                cmd.id if cmd.id is not None else "",
                cmd.safety.value,
                "", "", "", ""
            ])
        else:
            for f in cmd.parameters:
                writer.writerow([
                    spec.metadata.name,
                    spec.metadata.version,
                    cmd.name,
                    cmd.id if cmd.id is not None else "",
                    cmd.safety.value,
                    f.name,
                    f.type.value,
                    f.length if f.length is not None else "",
                    f.unit or "",
                ])

    return output.getvalue()


def import_csv_protocol(csv_text: str) -> Tuple[ProtocolSpec, List[str]]:
    """Import protocol definition from tabular CSV text, returning (ProtocolSpec, losses_warnings)."""
    reader = csv.DictReader(io.StringIO(csv_text))
    losses: List[str] = []

    proto_name = "ImportedCSVProtocol"
    proto_ver = "1.0.0"
    commands_map: Dict[str, Dict[str, Any]] = {}

    for line_no, row in enumerate(reader, 2):
        name = row.get("protocol_name") or proto_name
        proto_name = name
        ver = row.get("protocol_version") or proto_ver
        proto_ver = ver

        cmd_name = row.get("command_name", "").strip()
        if not cmd_name:
            continue

        if cmd_name not in commands_map:
            cmd_id_raw = row.get("command_id", "").strip()
            cmd_id = int(cmd_id_raw) if cmd_id_raw.isdigit() else (cmd_id_raw or None)
            safety_str = row.get("command_safety", "read_only").strip().lower()

            safety = CommandSafety.READ_ONLY
            if safety_str == "mutating":
                safety = CommandSafety.MUTATING
            elif safety_str == "idempotent":
                safety = CommandSafety.IDEMPOTENT
            elif safety_str == "destructive":
                safety = CommandSafety.DESTRUCTIVE

            commands_map[cmd_name] = {
                "name": cmd_name,
                "id": cmd_id,
                "safety": safety,
                "fields": [],
            }

        fname = row.get("field_name", "").strip()
        ftype_str = row.get("field_type", "").strip().lower()
        if fname and ftype_str:
            try:
                ftype = FieldType(ftype_str)
            except ValueError:
                ftype = FieldType.UINT8
                losses.append(f"Line {line_no}: Field type '{ftype_str}' for field '{fname}' fell back to 'uint8'.")

            flen_str = row.get("field_length", "").strip()
            flen = int(flen_str) if flen_str.isdigit() else None
            unit = row.get("field_unit", "").strip() or None

            commands_map[cmd_name]["fields"].append(
                FieldSpec(name=fname, type=ftype, length=flen, unit=unit)
            )

    cmds = [
        CommandSpec(
            name=c["name"],
            id=c["id"],
            safety=c["safety"],
            parameters=c["fields"],
        )
        for c in commands_map.values()
    ]

    spec = ProtocolSpec(
        metadata=ProtocolMeta(name=proto_name, version=proto_ver),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY),
        commands=cmds,
    )

    return spec, losses
