"""Protocol Visualization Engine for OmniUART (#217).

Generates Mermaid sequence/flowchart diagrams, interactive HTML frame layouts,
and SVG packet boundary visualizations for protocol specs.
"""

from __future__ import annotations

import html
from typing import List, Optional
from omniuart.core.models import ProtocolSpec, CommandSpec, FieldSpec


def render_mermaid_diagram(spec: ProtocolSpec) -> str:
    """Render protocol command request/response sequence diagram in Mermaid format."""
    lines: List[str] = ["sequenceDiagram", f"    autonumber", f"    participant Host"]
    device_label = spec.metadata.name or "Device"
    lines.append(f"    participant Device as {device_label}")

    for cmd in spec.commands:
        req_fields = ", ".join([f"{f.name}:{f.type.value}" for f in cmd.parameters]) or "void"
        lines.append(f"    Host->>Device: {cmd.name}({req_fields})")
        if cmd.response:
            resp_fields = ", ".join([f"{f.name}:{f.type.value}" for f in cmd.response.fields]) or "ack"
            lines.append(f"    Device-->>Host: {cmd.name}_response({resp_fields})")

    return "\n".join(lines)


def render_svg_frame(spec: ProtocolSpec, command_name: Optional[str] = None) -> str:
    """Render SVG packet layout diagram showing byte offsets and field boundaries."""
    cmd = spec.get_command(command_name) if command_name else (spec.commands[0] if spec.commands else None)
    fields = cmd.parameters if cmd else []

    svg_width = 800
    svg_height = 140
    rect_height = 40
    start_y = 50

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}">',
        f'  <style>rect {{ stroke: #333; stroke-width: 1.5; }} text {{ font-family: monospace; font-size: 12px; }}</style>',
        f'  <text x="10" y="25" font-size="14" font-weight="bold" fill="#333">Frame Layout: {spec.metadata.name} {cmd.name if cmd else ""}</text>',
    ]

    x = 10
    total_fields = len(fields) or 1
    box_width = min(150, (svg_width - 20) // total_fields)

    colors = ["#e3f2fd", "#e8f5e9", "#fff3e0", "#f3e5f5", "#fbe9e7"]

    for i, fspec in enumerate(fields):
        color = colors[i % len(colors)]
        svg_lines.append(f'  <rect x="{x}" y="{start_y}" width="{box_width}" height="{rect_height}" fill="{color}" />')
        svg_lines.append(f'  <text x="{x + 8}" y="{start_y + 24}" font-weight="bold">{html.escape(fspec.name)}</text>')
        svg_lines.append(f'  <text x="{x + 8}" y="{start_y + 36}" font-size="10" fill="#666">{fspec.type.value}</text>')
        x += box_width

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def render_html_visualizer(spec: ProtocolSpec) -> str:
    """Render interactive HTML visualizer widget for protocol specs."""
    mermaid_code = render_mermaid_diagram(spec)
    svg_code = render_svg_frame(spec)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Protocol Visualizer - {html.escape(spec.metadata.name)}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.min.js"></script>
    <style>
        body {{ font-family: system-ui, sans-serif; margin: 20px; background: #fafafa; color: #222; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        h2 {{ margin-top: 0; color: #1976d2; }}
    </style>
</head>
<body>
    <h1>Protocol Visualizer: {html.escape(spec.metadata.name)} (v{html.escape(spec.metadata.version)})</h1>
    
    <div class="card">
        <h2>Frame Structure Breakdown</h2>
        {svg_code}
    </div>

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
