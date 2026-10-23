"""Artefact Generator Engine for OmniUART Protocols (#282, #319, #338).

Generates Wireshark Lua dissectors, C headers, Python dataclasses, and JSON Schemas from ProtocolSpec definitions.
Wire-accurate framing, offsets, CRC calculation helpers, responses, and telemetry structs.
"""

from __future__ import annotations

import json
import keyword
import re
from typing import Any, List, Optional

from omniuart.core.crc import PRESET_MODELS, CrcAlgorithm, CrcModel, resolve_algorithm
from omniuart.core.models import FieldSpec, FieldType, ProtocolSpec


def _c_ident(name: str) -> str:
    """Sanitise string to valid C identifier."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not clean:
        clean = "unnamed"
    if clean[0].isdigit():
        clean = f"_{clean}"
    if clean.lower() in {
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "inline", "int", "long", "register", "restrict", "return", "short",
        "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
        "unsigned", "void", "volatile", "while",
    }:
        clean = f"{clean}_"
    return clean


def _py_ident(name: str) -> str:
    """Sanitise string to valid Python identifier."""
    clean = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if not clean:
        clean = "unnamed"
    if clean[0].isdigit():
        clean = f"_{clean}"
    if keyword.iskeyword(clean):
        clean = f"{clean}_"
    return clean


def _py_type(ft: FieldType) -> str:
    val = ft.value if hasattr(ft, "value") else str(ft)
    if val in ("float32", "float64", "float", "double"):
        return "float"
    if val in ("bool", "boolean"):
        return "bool"
    if val in ("string", "str", "text", "ascii"):
        return "str"
    if val in ("bytes", "hex", "raw", "binary"):
        return "bytes"
    return "int"


def _py_default(ft: FieldType, default: Any = None) -> str:
    val = ft.value if hasattr(ft, "value") else str(ft)
    if default is not None:
        if isinstance(default, str):
            return json.dumps(default)
        if isinstance(default, bytes):
            return repr(default)
        return str(default)
    if val in ("float32", "float64", "float", "double"):
        return "0.0"
    if val in ("bool", "boolean"):
        return "False"
    if val in ("string", "str", "text", "ascii"):
        return '""'
    if val in ("bytes", "hex", "raw", "binary"):
        return "b''"
    return "0"


def _c_type_declaration(field: FieldSpec) -> str:
    val = field.type.value if hasattr(field.type, "value") else str(field.type)
    c_name = _c_ident(field.name)
    endian_comment = f"/* {val}, {field.endian or 'little'}-endian */"

    if val in ("string", "str", "text", "ascii"):
        length = field.length or 32
        return f"char {c_name}[{length}]; {endian_comment}"
    if val in ("bytes", "hex", "raw", "binary"):
        length = field.length or 16
        return f"uint8_t {c_name}[{length}]; {endian_comment}"

    mapping = {
        "uint8": "uint8_t",
        "int8": "int8_t",
        "uint16": "uint16_t",
        "int16": "int16_t",
        "uint32": "uint32_t",
        "int32": "int32_t",
        "uint64": "uint64_t",
        "int64": "int64_t",
        "float32": "float",
        "float": "float",
        "float64": "double",
        "double": "double",
        "bool": "bool",
        "boolean": "bool",
        "enum": "uint8_t",
    }
    c_t = mapping.get(val, "uint8_t")
    return f"{c_t} {c_name}; {endian_comment}"


def _get_crc_model(spec: ProtocolSpec) -> Optional[CrcModel]:
    if not spec.framing.integrity:
        return None
    integ = spec.framing.integrity
    algo = resolve_algorithm(integ.algorithm)
    if algo is CrcAlgorithm.CUSTOM:
        return integ.to_crc_model()
    return PRESET_MODELS.get(algo)


def _generate_crc_c_function(name_prefix: str, model: CrcModel) -> List[str]:
    """Generate wire-accurate C function for declared CRC algorithm (#282, #338)."""
    w = model.width
    c_uint = f"uint{w}_t" if w in (8, 16, 32, 64) else "uint32_t"
    mask = (1 << w) - 1
    init_hex = f"0x{model.init:0{w//4 or 1}X}"
    poly_hex = f"0x{model.poly:0{w//4 or 1}X}"
    xorout_hex = f"0x{model.xorout:0{w//4 or 1}X}"

    lines: List[str] = [
        f"/* CRC Helper Function ({model.width}-bit, poly={poly_hex}, init={init_hex}, refin={model.refin}, refout={model.refout}) */",
        f"static inline {c_uint} {name_prefix}_calculate_crc(const uint8_t *data, size_t len) {{",
    ]

    if model.refin and model.refout:
        poly_rev = 0
        for i in range(w):
            if (model.poly >> i) & 1:
                poly_rev |= (1 << (w - 1 - i))
        poly_rev_hex = f"0x{poly_rev:0{w//4 or 1}X}"
        lines.extend([
            f"    {c_uint} crc = {init_hex};",
            "    for (size_t i = 0; i < len; i++) {",
            f"        crc ^= ({c_uint})data[i];",
            "        for (int j = 0; j < 8; j++) {",
            "            if (crc & 1) {",
            f"                crc = (crc >> 1) ^ {poly_rev_hex};",
            "            } else {",
            "                crc >>= 1;",
            "            }",
            "        }",
            "    }",
            f"    return (crc ^ {xorout_hex}) & 0x{mask:X};",
            "}",
            "",
        ])
    else:
        shift = w - 8 if w >= 8 else 0
        lines.extend([
            f"    {c_uint} crc = {init_hex};",
            "    for (size_t i = 0; i < len; i++) {",
            f"        crc ^= (({c_uint})data[i]) << {shift};",
            "        for (int j = 0; j < 8; j++) {",
            f"            if (crc & (1ULL << {w - 1})) {{",
            f"                crc = ((crc << 1) ^ {poly_hex}) & 0x{mask:X};",
            "            } else {",
            f"                crc = (crc << 1) & 0x{mask:X};",
            "            }",
            "        }",
            "    }",
            f"    return (crc ^ {xorout_hex}) & 0x{mask:X};",
            "}",
            "",
        ])
    return lines


def generate_c_header(spec: ProtocolSpec) -> str:
    """Generate C header file with packed structs, opcode enums, framing constants, response/telemetry structs, and CRC helpers (#282, #338)."""
    ident = _c_ident(spec.metadata.name).lower()
    guard = f"{ident.upper()}_H"
    lines = [
        f"/* C Protocol Header for {spec.metadata.name} (v{spec.metadata.version}) */",
        "/* Auto-generated by OmniUART */",
        "",
        f"#ifndef {guard}",
        f"#define {guard}",
        "",
        "#include <stdint.h>",
        "#include <stdbool.h>",
        "#include <stddef.h>",
        "",
        "/* --- Framing Constants --- */",
        f"#define {guard}_BAUDRATE {spec.serial_config.baudrate}",
    ]

    if spec.framing.header:
        hdr_len = len(spec.framing.header)
        hdr_bytes = ", ".join(f"0x{b:02X}" for b in spec.framing.header)
        lines.append(f"#define {guard}_HEADER_LEN {hdr_len}")
        lines.append(f"static const uint8_t {ident}_header_bytes[{hdr_len}] = {{{hdr_bytes}}};")

    if spec.framing.footer:
        ftr_len = len(spec.framing.footer)
        ftr_bytes = ", ".join(f"0x{b:02X}" for b in spec.framing.footer)
        lines.append(f"#define {guard}_FOOTER_LEN {ftr_len}")
        lines.append(f"static const uint8_t {ident}_footer_bytes[{ftr_len}] = {{{ftr_bytes}}};")

    lines.append("")

    # Command ID C type
    cmd_id_type_name = "uint8_t"
    if spec.framing.command_id:
        cmd_id_type_name = {
            "uint8": "uint8_t",
            "uint16": "uint16_t",
            "uint32": "uint32_t",
        }.get(spec.framing.command_id.type, "uint8_t")

    # Command Opcodes
    lines.append("/* --- Command Opcodes --- */")
    lines.append("typedef enum {")
    has_enum = False
    for cmd in spec.commands:
        if isinstance(cmd.id, int):
            lines.append(f"    CMD_{_c_ident(cmd.name).upper()} = {cmd.id},")
            has_enum = True
    if not has_enum:
        lines.append("    CMD_NONE = 0,")
    lines.extend([
        "} command_id_t;",
        "",
    ])

    # Response Opcodes
    resp_cmds = [c for c in spec.commands if c.response and isinstance(c.response.id, int)]
    if resp_cmds:
        lines.append("/* --- Response Opcodes --- */")
        lines.append("typedef enum {")
        for c in resp_cmds:
            lines.append(f"    RESP_{_c_ident(c.name).upper()} = {c.response.id},")  # type: ignore[union-attr]
        lines.extend([
            "} response_id_t;",
            "",
        ])

    # Command Request Structs
    lines.append("/* --- Command Request Structs --- */")
    for cmd in spec.commands:
        struct_name = f"{_c_ident(cmd.name).lower()}_req_t"
        lines.append("typedef struct __attribute__((packed)) {")
        lines.append(f"    {cmd_id_type_name} command_id;")
        if cmd.parameters:
            for p in cmd.parameters:
                lines.append(f"    {_c_type_declaration(p)}")
        lines.append(f"}} {struct_name};")
        lines.append("")

    # Command Response Structs
    lines.append("/* --- Command Response Structs --- */")
    has_responses = False
    for cmd in spec.commands:
        if cmd.response:
            has_responses = True
            resp_struct_name = f"{_c_ident(cmd.name).lower()}_resp_t"
            lines.append("typedef struct __attribute__((packed)) {")
            if isinstance(cmd.response.id, int):
                lines.append(f"    {cmd_id_type_name} response_id;")
            if cmd.response.fields:
                for rf in cmd.response.fields:
                    lines.append(f"    {_c_type_declaration(rf)}")
            lines.append(f"}} {resp_struct_name};")
            lines.append("")
    if not has_responses:
        lines.append("/* (no response structs defined) */\n")

    # Telemetry Structs
    if spec.telemetry:
        lines.append("/* --- Device Telemetry Structs --- */")
        for tel in spec.telemetry:
            tel_struct_name = f"{_c_ident(tel.name).lower()}_telemetry_t"
            lines.append("typedef struct __attribute__((packed)) {")
            if isinstance(tel.id, int):
                lines.append(f"    {cmd_id_type_name} message_id;")
            if tel.fields:
                for tf in tel.fields:
                    lines.append(f"    {_c_type_declaration(tf)}")
            lines.append(f"}} {tel_struct_name};")
            lines.append("")

    # CRC Helper Function
    crc_model = _get_crc_model(spec)
    if crc_model:
        lines.extend(_generate_crc_c_function(ident, crc_model))

    lines.extend([f"#endif /* {guard} */", ""])
    return "\n".join(lines)


def generate_wireshark_dissector(spec: ProtocolSpec) -> str:
    """Generate wire-accurate Wireshark Lua dissector for USER0 (encap 147) PCAPNG captures (#282, #338)."""
    name_clean = _c_ident(spec.metadata.name)
    proto_title = f"{spec.metadata.name} Protocol"

    hdr_len = len(spec.framing.header) if spec.framing.header else 0
    ftr_len = len(spec.framing.footer) if spec.framing.footer else 0

    len_size = 0
    len_type = "uint16"
    if spec.framing.length:
        len_type = spec.framing.length.type
        len_size = {"uint8": 1, "uint16": 2, "uint32": 4}.get(len_type, 2)

    cmd_id_size = 1
    cmd_id_protofield = "uint8"
    if spec.framing.command_id:
        cmd_id_protofield = spec.framing.command_id.type
        cmd_id_size = {"uint8": 1, "uint16": 2, "uint32": 4}.get(cmd_id_protofield, 1)

    crc_model = _get_crc_model(spec)
    crc_size = (crc_model.width // 8) if crc_model else 0
    crc_protofield = "uint16" if crc_size == 2 else ("uint32" if crc_size == 4 else "uint8")

    lines = [
        f"-- Wireshark Lua Dissector for {spec.metadata.name} (v{spec.metadata.version})",
        "-- Auto-generated by OmniUART with wire-accurate framing and field offsets (#338)",
        "",
        f'local p_{name_clean} = Proto("{name_clean}", "{proto_title}")',
        "",
        f'local f_header = ProtoField.bytes("{name_clean}.header", "Framing Header")',
        f'local f_length = ProtoField.{len_type}("{name_clean}.length", "Frame Length", base.DEC)',
        f'local f_cmd_id = ProtoField.{cmd_id_protofield}("{name_clean}.cmd_id", "Command ID", base.HEX)',
        f'local f_payload = ProtoField.bytes("{name_clean}.payload", "Payload")',
        f'local f_crc = ProtoField.{crc_protofield}("{name_clean}.crc", "Integrity Check", base.HEX)',
        f'local f_footer = ProtoField.bytes("{name_clean}.footer", "Framing Footer")',
        "",
        f"p_{name_clean}.fields = {{ f_header, f_length, f_cmd_id, f_payload, f_crc, f_footer }}",
        "",
        f"function p_{name_clean}.dissector(buffer, pinfo, tree)",
        f'    pinfo.cols.protocol = "{spec.metadata.name}"',
        f'    local subtree = tree:add(p_{name_clean}, buffer(), "{spec.metadata.name} Frame")',
        "    local offset = 0",
        "    local buf_len = buffer:len()",
        "",
    ]

    if hdr_len > 0:
        lines.extend([
            f"    if buf_len >= offset + {hdr_len} then",
            f"        subtree:add(f_header, buffer(offset, {hdr_len}))",
            f"        offset = offset + {hdr_len}",
            "    end",
            "",
        ])

    if len_size > 0:
        lines.extend([
            f"    if buf_len >= offset + {len_size} then",
            f"        subtree:add(f_length, buffer(offset, {len_size}))",
            f"        offset = offset + {len_size}",
            "    end",
            "",
        ])

    if cmd_id_size > 0:
        lines.extend([
            f"    if buf_len >= offset + {cmd_id_size} then",
            f"        subtree:add(f_cmd_id, buffer(offset, {cmd_id_size}))",
            f"        offset = offset + {cmd_id_size}",
            "    end",
            "",
        ])

    lines.extend([
        f"    local footer_len = {ftr_len}",
        f"    local crc_len = {crc_size}",
        "    local remaining = buf_len - offset",
        "    local payload_len = remaining - crc_len - footer_len",
        "",
        "    if payload_len > 0 and buf_len >= offset + payload_len then",
        "        subtree:add(f_payload, buffer(offset, payload_len))",
        "        offset = offset + payload_len",
        "    end",
        "",
    ])

    if crc_size > 0:
        lines.extend([
            "    if crc_len > 0 and buf_len >= offset + crc_len then",
            "        subtree:add(f_crc, buffer(offset, crc_len))",
            "        offset = offset + crc_len",
            "    end",
            "",
        ])

    if ftr_len > 0:
        lines.extend([
            "    if footer_len > 0 and buf_len >= offset + footer_len then",
            "        subtree:add(f_footer, buffer(offset, footer_len))",
            "    end",
            "",
        ])

    lines.extend([
        "end",
        "",
        "-- Register dissector for USER0 PCAPNG linktype (147)",
        'local wtap_encap_table = DissectorTable.get("wtap_encap")',
        "if wtap_encap_table then",
        f"    wtap_encap_table:add(147, p_{name_clean})",
        "end",
    ])
    return "\n".join(lines)


def generate_python_dataclasses(spec: ProtocolSpec) -> str:
    """Generate Python dataclass representations of protocol commands, responses, and telemetry with correct typed defaults (#319, #338)."""
    lines = [
        f'"""Python dataclasses for {spec.metadata.name} (v{spec.metadata.version}).',
        "Auto-generated by OmniUART.",
        '"""',
        "",
        "from __future__ import annotations",
        "from dataclasses import dataclass, field",
        "from typing import Optional, List",
        "",
    ]

    for cmd in spec.commands:
        class_clean = _py_ident(_c_ident(cmd.name).title().replace("_", ""))
        class_name = f"{class_clean}Request"
        lines.append("@dataclass")
        lines.append(f"class {class_name}:")
        lines.append(f'    """Payload for command {cmd.name} (ID: {cmd.id})."""')
        if isinstance(cmd.id, int):
            lines.append(f"    command_id: int = {cmd.id}")
        else:
            quoted_id = json.dumps(str(cmd.id))
            lines.append(f"    command_id: str = {quoted_id}")
        if cmd.parameters:
            for p in cmd.parameters:
                py_t = _py_type(p.type)
                default_val = _py_default(p.type, p.default)
                lines.append(f"    {_py_ident(p.name)}: {py_t} = {default_val}")
        lines.append("")

        if cmd.response:
            resp_class = f"{class_clean}Response"
            lines.append("@dataclass")
            lines.append(f"class {resp_class}:")
            lines.append(f'    """Response payload for command {cmd.name}."""')
            if isinstance(cmd.response.id, int):
                lines.append(f"    response_id: int = {cmd.response.id}")
            if cmd.response.fields:
                for rf in cmd.response.fields:
                    py_t = _py_type(rf.type)
                    default_val = _py_default(rf.type, rf.default)
                    lines.append(f"    {_py_ident(rf.name)}: {py_t} = {default_val}")
            else:
                lines.append("    pass")
            lines.append("")

    for tel in spec.telemetry:
        class_clean = _py_ident(_c_ident(tel.name).title().replace("_", ""))
        tel_class = f"{class_clean}Telemetry"
        lines.append("@dataclass")
        lines.append(f"class {tel_class}:")
        lines.append(f'    """Telemetry message {tel.name}."""')
        if isinstance(tel.id, int):
            lines.append(f"    message_id: int = {tel.id}")
        if tel.fields:
            for tf in tel.fields:
                py_t = _py_type(tf.type)
                default_val = _py_default(tf.type, tf.default)
                lines.append(f"    {_py_ident(tf.name)}: {py_t} = {default_val}")
        else:
            lines.append("    pass")
        lines.append("")

    return "\n".join(lines)


def generate_json_schema() -> str:
    """Emit official JSON Schema for OmniUART ProtocolSpec."""
    from omniuart.core.models import ProtocolSpec
    return json.dumps(ProtocolSpec.model_json_schema(), indent=2)
