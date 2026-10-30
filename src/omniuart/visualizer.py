"""Protocol Visualization Engine for OmniUART (#217, #330).

Generates Mermaid sequence/flowchart diagrams, interactive HTML frame layouts,
and SVG packet boundary visualizations for protocol specs with byte offsets and sizes.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Tuple

from omniuart.core.codec import FrameCodec
from omniuart.core.models import FieldType, ProtocolSpec


def render_mermaid_diagram(spec: ProtocolSpec) -> str:
    """Render protocol command request/response sequence diagram in Mermaid format."""
    lines: List[str] = ["sequenceDiagram", "    autonumber", "    participant Host"]
    device_label = html.escape(spec.metadata.name or "Device")
    lines.append(f"    participant Device as {device_label}")

    for cmd in spec.commands:
        cmd_name = html.escape(cmd.name)
        req_fields = ", ".join([f"{html.escape(f.name)}:{f.type.value}" for f in cmd.parameters]) or "void"
        lines.append(f"    Host->>Device: {cmd_name}({req_fields})")
        if cmd.response:
            resp_fields = ", ".join([f"{html.escape(f.name)}:{f.type.value}" for f in cmd.response.fields]) or "ack"
            lines.append(f"    Device-->>Host: {cmd_name}_response({resp_fields})")

    return "\n".join(lines)


def _field_size_bytes(f_type: FieldType, length: Optional[int] = None) -> int:
    val = f_type.value if hasattr(f_type, "value") else str(f_type)
    if length is not None and length > 0:
        return length
    if val in ("uint8", "int8", "bool", "boolean", "enum"):
        return 1
    if val in ("uint16", "int16"):
        return 2
    if val in ("uint32", "int32", "float32", "float"):
        return 4
    if val in ("uint64", "int64", "float64", "double"):
        return 8
    return 4


def render_svg_frame(spec: ProtocolSpec, command_name: Optional[str] = None) -> str:
    """Render SVG packet layout diagram showing byte offsets and field boundaries (#330)."""
    cmd = spec.get_command(command_name) if command_name else (spec.commands[0] if spec.commands else None)

    # Collect all frame segments with their byte sizes and descriptions
    segments: List[Tuple[str, str, int, str]] = []  # (label, sublabel, size_bytes, fill_color)

    # 1. Framing Header
    if spec.framing.header:
        hdr_len = len(spec.framing.header)
        hdr_hex = " ".join(f"0x{b:02X}" for b in spec.framing.header)
        segments.append(("Header", hdr_hex, hdr_len, "#e3f2fd"))

    # 2. Framing Length
    if spec.framing.length:
        len_size = {"uint8": 1, "uint16": 2, "uint32": 4}.get(spec.framing.length.type, 2)
        segments.append(("Length", f"{spec.framing.length.type}", len_size, "#e1f5fe"))

    # 3. Framing Command ID
    if spec.framing.command_id:
        cmd_id_size = {"uint8": 1, "uint16": 2, "uint32": 4}.get(spec.framing.command_id.type, 1)
        id_val = f"0x{cmd.id:02X}" if (cmd and isinstance(cmd.id, int)) else (str(cmd.id) if cmd else "")
        segments.append(("Cmd ID", id_val, cmd_id_size, "#ede7f6"))

    # 4. Command Parameters
    if cmd:
        colors = ["#e8f5e9", "#fff3e0", "#f3e5f5", "#fbe9e7", "#e0f2f1"]
        for i, p in enumerate(cmd.parameters):
            p_size = _field_size_bytes(p.type, p.length)
            color = colors[i % len(colors)]
            segments.append((p.name, f"{p.type.value}", p_size, color))

    # 5. Framing Integrity / CRC
    if spec.framing.integrity:
        alg = spec.framing.integrity.algorithm
        crc_size = 4 if "32" in alg else (2 if ("16" in alg or "modbus" in alg or "ccitt" in alg) else 1)
        segments.append(("CRC", alg, crc_size, "#ffebee"))

    # 6. Framing Footer
    if spec.framing.footer:
        ftr_len = len(spec.framing.footer)
        ftr_hex = " ".join(f"0x{b:02X}" for b in spec.framing.footer)
        segments.append(("Footer", ftr_hex, ftr_len, "#eceff1"))

    total_segments = len(segments) or 1
    box_width = min(130, max(80, 800 // total_segments))
    svg_width = max(800, box_width * total_segments + 40)
    svg_height = 160
    rect_height = 50
    start_y = 65

    escaped_spec_name = html.escape(spec.metadata.name)
    escaped_cmd_name = html.escape(cmd.name if cmd else "")

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">',
        '  <style>rect { stroke: #333; stroke-width: 1.5; } text { font-family: monospace; font-size: 11px; }</style>',
        f'  <text x="15" y="25" font-size="14" font-weight="bold" fill="#333">Frame Layout: {escaped_spec_name} {escaped_cmd_name}</text>',
    ]

    current_offset = 0
    x = 15

    for label, sublabel, size_bytes, fill_color in segments:
        offset_str = f"[{current_offset}..{current_offset + size_bytes - 1}]" if size_bytes > 1 else f"[{current_offset}]"
        current_offset += size_bytes

        # Offset header text
        svg_lines.append(f'  <text x="{x + 4}" y="{start_y - 8}" font-size="10" fill="#555">{html.escape(offset_str)}</text>')
        # Segment box
        svg_lines.append(f'  <rect x="{x}" y="{start_y}" width="{box_width}" height="{rect_height}" fill="{fill_color}" />')
        # Segment main label
        svg_lines.append(f'  <text x="{x + 6}" y="{start_y + 20}" font-weight="bold">{html.escape(label[:12])}</text>')
        # Segment sublabel (size & type)
        svg_lines.append(f'  <text x="{x + 6}" y="{start_y + 36}" font-size="9" fill="#555">{html.escape(sublabel[:14])}</text>')
        x += box_width + 4

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def render_html_visualizer(spec: ProtocolSpec) -> str:
    """Render interactive HTML visualizer widget with sequence diagram, SVG packet breakdown, and sample frame (#330)."""
    mermaid_code = render_mermaid_diagram(spec)
    svg_code = render_svg_frame(spec)

    sample_frame_html = ""
    if spec.commands:
        cmd = spec.commands[0]
        try:
            codec = FrameCodec(spec)
            sample_params: Dict[str, Any] = {}
            for p in cmd.parameters:
                sample_params[p.name] = p.default if p.default is not None else 0
            encoded = codec.encode_command(cmd, sample_params)
            hex_str = encoded.hex(" ").upper()
            sample_frame_html = f"""
    <div class="card">
        <h2>Sample Encoded Frame ({html.escape(cmd.name)})</h2>
        <pre><code>{html.escape(hex_str)}</code></pre>
        <p><strong>Length:</strong> {len(encoded)} bytes</p>
    </div>
"""
        except Exception:
            pass

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Protocol Visualizer - {html.escape(spec.metadata.name)}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>
    <style>
        body {{ font-family: system-ui, sans-serif; margin: 20px; background: #fafafa; color: #222; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        h2 {{ margin-top: 0; color: #1976d2; }}
        pre {{ background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; font-family: monospace; }}
    </style>
</head>
<body>
    <h1>Protocol Visualizer: {html.escape(spec.metadata.name)} (v{html.escape(spec.metadata.version)})</h1>

    <div class="card">
        <h2>Frame Structure Breakdown</h2>
        {svg_code}
    </div>

    {sample_frame_html}

    <div class="card">
        <h2>Sequence Diagram</h2>
        <div class="mermaid">
        {mermaid_code}
        </div>
    </div>
    <script>mermaid.initialize({{startOnLoad:true}});</script>
</body>
</html>"""


def visualize_protocol(spec: ProtocolSpec, format: str = "mermaid", command_name: Optional[str] = None) -> str:
    """Main visualization entrypoint supporting 'mermaid', 'svg', and 'html' formats."""
    fmt = format.lower().strip()
    if fmt == "mermaid":
        return render_mermaid_diagram(spec)
    elif fmt == "svg":
        return render_svg_frame(spec, command_name=command_name)
    elif fmt == "html":
        return render_html_visualizer(spec)
    else:
        raise ValueError(f"Unsupported visualization format '{format}'. Expected 'mermaid', 'svg', or 'html'.")
