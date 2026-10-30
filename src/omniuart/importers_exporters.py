"""Import / Export Tooling for Protocol Definitions (#221).

Provides conversion and migration tooling between OmniUART ProtocolSpec, YAML, JSON Schema,
CSV tabular formats, and Wireshark dissector metadata, including validation and loss reporting.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional, Tuple


from omniuart.core.models import (
    CommandSafety,
    CommandSpec,
    FieldSpec,
    FieldType,
    FramingConfig,
    FramingType,
    ProtocolMeta,
    ProtocolSpec,
    SerialConfig,
)


def export_csv_protocol(spec: ProtocolSpec, losses: Optional[List[str]] = None) -> str:
    """Export protocol commands and parameters to tabular CSV string, recording dropped features in losses if provided."""
    if losses is not None:
        if spec.framing.integrity and spec.framing.integrity.algorithm != "none":
            losses.append(f"integrity check '{spec.framing.integrity.algorithm}' dropped in CSV export")
        if spec.telemetry:
            losses.append(f"{len(spec.telemetry)} telemetry definition(s) dropped in CSV export")
        for cmd in spec.commands:
            if cmd.response:
                losses.append(f"response definition for '{cmd.name}' dropped in CSV export")
            for f in cmd.parameters:
                if f.options:
                    losses.append(f"enum options for field '{f.name}' dropped in CSV export")
                if f.min is not None or f.max is not None:
                    losses.append(f"range bounds for field '{f.name}' dropped in CSV export")
                if f.encoding:
                    losses.append(f"encoding '{f.encoding}' for field '{f.name}' dropped in CSV export")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "protocol_name",
        "protocol_version",
        "baudrate",
        "framing_type",
        "command_name",
        "command_id",
        "command_safety",
        "field_name",
        "field_type",
        "field_length",
        "field_unit",
    ])

    baud_str = str(spec.serial_config.baudrate)
    framing_str = spec.framing.type.value

    for cmd in spec.commands:
        if not cmd.parameters:
            writer.writerow([
                spec.metadata.name,
                spec.metadata.version,
                baud_str,
                framing_str,
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
                    baud_str,
                    framing_str,
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
    baudrate: Optional[int] = None
    framing_type: Optional[FramingType] = None
    commands_map: Dict[str, Dict[str, Any]] = {}

    for line_no, row in enumerate(reader, 2):
        name = row.get("protocol_name") or proto_name
        proto_name = name
        ver = row.get("protocol_version") or proto_ver
        proto_ver = ver

        baud_raw = (row.get("baudrate") or "").strip()
        if baud_raw and baudrate is None:
            try:
                baudrate = int(baud_raw)
            except ValueError:
                pass

        framing_raw = (row.get("framing_type") or "").strip().lower()
        if framing_raw and framing_type is None:
            try:
                framing_type = FramingType(framing_raw)
            except ValueError:
                pass

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

    if baudrate is None:
        baudrate = 115200
        losses.append("Baud rate not specified in CSV; defaulted to 115200.")

    if framing_type is None:
        framing_type = FramingType.BINARY
        losses.append("Framing type not specified in CSV; defaulted to 'binary'.")

    losses.append("Responses, telemetry, checksum algorithms and encodings are not represented in CSV.")

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
        serial_config=SerialConfig(baudrate=baudrate),
        framing=FramingConfig(type=framing_type),
        commands=cmds,
    )

    return spec, losses


def find_csv_losses(original: ProtocolSpec, imported: ProtocolSpec) -> List[str]:
    """Compare original protocol with CSV-imported protocol and return list of differences / losses."""
    losses: List[str] = []
    if original.serial_config.baudrate != imported.serial_config.baudrate:
        losses.append(f"baudrate changed: {original.serial_config.baudrate} -> {imported.serial_config.baudrate}")
    if original.framing.type != imported.framing.type:
        losses.append(f"framing changed: {original.framing.type.value} -> {imported.framing.type.value}")
    if original.framing.integrity and original.framing.integrity.algorithm != "none":
        losses.append(f"integrity check '{original.framing.integrity.algorithm}' dropped")
    if original.telemetry:
        losses.append(f"{len(original.telemetry)} telemetry definition(s) dropped")
    for cmd in original.commands:
        imp_cmd = imported.get_command(cmd.name)
        if not imp_cmd:
            losses.append(f"command '{cmd.name}' dropped")
            continue
        if cmd.response:
            losses.append(f"response for '{cmd.name}' dropped")
        for f in cmd.parameters:
            if f.options or f.encoding or f.min is not None or f.max is not None:
                losses.append(f"constraints / options for field '{f.name}' in command '{cmd.name}' dropped")
    return losses
