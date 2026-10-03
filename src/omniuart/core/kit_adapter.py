"""Adapter for parsing uart-interface-schema-kit protocols into OmniUART ProtocolSpec instances."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from omniuart.core.crc import normalize_algorithm_name
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

logger = logging.getLogger(__name__)


def _map_algorithm_name(algo: str) -> str:
    """Map a kit schema integrity algorithm name to the OmniUART algorithm name."""
    return normalize_algorithm_name(algo)


_COVERAGE = {
    "payload-only": "payload_only",
    "whole-frame-excluding-check": "full_frame",
    "length-to-payload-inclusive": "after_header",
}
_TRANSFORMS = {"twosComplement": "twos_complement", "onesComplement": "ones_complement"}


def _normalise_id(value: Any) -> Union[int, str]:
    """A message id as an int where it looks like one (``1``, ``"0x01"``, ``"17"``), else unchanged text."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            if text.lower().startswith("0x"):
                return int(text, 16)
            if text.isdigit():
                return int(text)
        except ValueError:
            pass
    return value


def _first(params: Dict[str, Any], *names: str, default: Any = None) -> Any:
    """First present key: the kit schema names (``widthBits``) or the short Rocksoft names (``width``)."""
    for name in names:
        if name in params:
            return params[name]
    return default


def _parse_integrity(raw: Dict[str, Any], source_name: Optional[str]) -> IntegritySpec:
    """Build an IntegritySpec from a kit ``integrityCheck`` block, warning about anything not modelled."""
    algo = _map_algorithm_name(raw["algorithm"])
    custom = raw.get("customParameters") or {}
    kwargs: Dict[str, Any] = {}
    if algo == "custom":
        kwargs.update(
            width=_first(custom, "widthBits", "width"),
            poly=_first(custom, "polynomial", "poly"),
            init=_first(custom, "initialValue", "init"),
            refin=bool(_first(custom, "reflectInput", "refin", default=False)),
            refout=bool(_first(custom, "reflectOutput", "refout", default=False)),
            xorout=_first(custom, "finalXor", "xorout", default=0),
            check=_first(custom, "check", "checkValue"),
            endian=custom.get("endian", "little"),
        )
    where = source_name or "kit protocol"
    coverage = raw.get("coverage")
    if coverage is not None:
        if coverage in _COVERAGE:
            kwargs["covers"] = _COVERAGE[coverage]
        else:
            logger.warning("%s: unknown integrity coverage %r, using the default", where, coverage)
    transform = raw.get("finalTransform")
    if transform is not None:
        if transform in _TRANSFORMS:
            kwargs["transform"] = _TRANSFORMS[transform]
        else:
            logger.warning("%s: unknown integrity finalTransform %r ignored", where, transform)
    if raw.get("summationMode") == "carry-wrapped":
        kwargs["carry_wrap"] = True
    if raw.get("valueEncoding") not in (None, "binary"):
        logger.warning("%s: integrity valueEncoding %r is not supported by the codec", where, raw["valueEncoding"])
    if "coverageEndMarker" in raw:
        logger.warning("%s: integrity coverageEndMarker is not supported by the codec", where)
    return IntegritySpec(algorithm=algo, **kwargs)


def _parse_baud(value: Any, source_name: str) -> int:
    """The baud rate declared by a kit protocol: an integer, a numeric string, or a list (the first entry wins).

    Never substitutes a different rate: a value that is not a positive integer raises ``ValueError``.
    """
    candidate = value[0] if isinstance(value, list) and value else value
    if isinstance(candidate, bool):
        raise ValueError(f"{source_name}: invalid baudRate {value!r}")
    if isinstance(candidate, str):
        candidate = candidate.strip()
        if not candidate.isdigit():
            raise ValueError(f"{source_name}: invalid baudRate {value!r}")
        candidate = int(candidate)
    if isinstance(candidate, float) and candidate.is_integer():
        candidate = int(candidate)
    if not isinstance(candidate, int) or candidate <= 0:
        raise ValueError(f"{source_name}: invalid baudRate {value!r}")
    return candidate


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
    baudrate = _parse_baud(phys.get("baudRate", 115200), source_name)

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
        integrity_spec = _parse_integrity(integrity_raw, source_name)

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

    def build_message(msg: Dict[str, Any], index: int, kind: str) -> Tuple[Union[int, str], List[FieldSpec]]:
        """Message id (the discriminator's constant, else a fallback) and its user-facing fields."""
        msg_id: Optional[Union[int, str]] = None
        fields_out: List[FieldSpec] = []
        raw_fields = msg.get("fields", [])
        # The discriminator is the field marked as such, else the first constant field. Any other
        # constant field is an ordinary field whose value defaults to that constant.
        discriminator = next((i for i, f in enumerate(raw_fields) if f.get("role") == "discriminator"), None)
        if discriminator is None:
            discriminator = next((i for i, f in enumerate(raw_fields) if "constValue" in f), None)
        for i, f in enumerate(raw_fields):
            field_spec = resolve_field_type(f)
            if "constValue" in f:
                field_spec.default = f["constValue"]
            if i == discriminator:
                if "constValue" in f:
                    msg_id = _normalise_id(f["constValue"])
                if framing_type is FramingType.DELIMITED:
                    # On a delimited line the discriminator *is* the message text, so it is
                    # carried by the id and must not be asked for as a parameter.
                    continue
            fields_out.append(field_spec)
        if msg_id is None:
            if kind == "command":
                # No discriminator to identify the command on the wire: fall back to its position.
                msg_id = index
                logger.warning("%s: command '%s' has no discriminator constValue, using its index %d as id", source_name or "kit protocol", msg.get("name"), index)
            else:
                msg_id = msg.get("name", f"message_{index}")
        return msg_id, fields_out

    # Commands: host-initiated messages
    commands: List[CommandSpec] = []
    for idx, cmd_data in enumerate(data.get("commands", [])):
        cmd_name = cmd_data.get("name", f"command_{idx}")
        cmd_id, params = build_message(cmd_data, idx, "command")

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

    # Responses: device-initiated messages (a stream-only protocol such as NMEA 0183 has only these).
    # The kit does not say which request a response answers, so they are exposed as telemetry
    # messages rather than guessed into command responses.
    telemetry: List[TelemetrySpec] = []
    for idx, msg in enumerate(data.get("responses", [])):
        msg_id, msg_fields = build_message(msg, idx, "response")
        telemetry.append(
            TelemetrySpec(
                name=msg.get("name", f"message_{idx}"),
                id=msg_id,
                description=msg.get("description"),
                tags=list(msg.get("tags", [])),
                fields=msg_fields,
            )
        )

    return ProtocolSpec(
        schema_version="1.0.0",
        metadata=metadata,
        serial_config=serial_config,
        framing=framing_config,
        commands=commands,
        telemetry=telemetry,
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
