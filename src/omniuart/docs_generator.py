"""Automated Protocol Specification Documentation & Site Generator for OmniUART."""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import List, Optional, Union

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import ProtocolSpec, load_protocol


def generate_markdown_docs(spec: ProtocolSpec) -> str:
    """Generate Markdown specification document for a protocol."""
    meta = spec.metadata
    lines: List[str] = []
    lines.append(f"# Hardware Protocol Specification: {meta.name}")
    lines.append("")
    lines.append(f"**Version**: `{meta.version}`  ")
    if meta.author:
        lines.append(f"**Author**: {meta.author}  ")
    lines.append(f"**Physical Layer**: `{spec.serial_config.baudrate} bps, {spec.serial_config.bytesize}N{spec.serial_config.stopbits}`  ")
    lines.append(f"**Framing**: `{spec.framing.type.value}`  ")
    if spec.framing.integrity:
        lines.append(f"**Integrity Algorithm**: `{spec.framing.integrity.algorithm}`  ")
    lines.append("")
    if meta.description:
        lines.append(f"## Description\n{meta.description}\n")

    lines.append("## Command Catalog & Message Signatures\n")

    tag_map = {}
    for cmd in spec.commands:
        tags = cmd.tags if cmd.tags else ["general"]
        for tag in tags:
            tag_map.setdefault(tag, []).append(cmd)

    for tag, cmds in tag_map.items():
        lines.append(f"### Category: {tag.upper()}\n")
        for cmd in cmds:
            desc = f" - {cmd.description}" if cmd.description else ""
            cmd_id_str = f"0x{cmd.id:02X}" if isinstance(cmd.id, int) else str(cmd.id)
            lines.append(f"#### `{cmd.name}` (Command ID: `{cmd_id_str}`){desc}\n")
            if cmd.parameters:
                lines.append("| Parameter | Type | Unit | Range / Constraints | Options |")
                lines.append("| :--- | :--- | :--- | :--- | :--- |")
                for p in cmd.parameters:
                    unit = p.unit or "-"
                    rng = f"[{p.min}, {p.max}]" if p.min is not None else "-"
                    opts = f"`{p.options}`" if p.options else "-"
                    lines.append(f"| `{p.name}` | `{p.type.value}` | {unit} | {rng} | {opts} |")
                lines.append("")
            if cmd.response:
                lines.append(f"**Expected Response Payload** (Timeout: `{cmd.response.timeout_ms} ms`):\n")
                lines.append("| Field Name | Type | Unit |")
                lines.append("| :--- | :--- | :--- |")
                for rf in cmd.response.fields:
                    rf_unit = rf.unit or "-"
                    lines.append(f"| `{rf.name}` | `{rf.type.value}` | {rf_unit} |")
                lines.append("")
    return "\n".join(lines)


def generate_html_docs(spec: ProtocolSpec) -> str:
    """Generate standalone HTML specification page for a protocol."""
    md_content = generate_markdown_docs(spec)
    body_html = html.escape(md_content).replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{html.escape(spec.metadata.name)} Specification</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; max-width: 900px; margin: 0 auto; line-height: 1.6; }}
    h1, h2, h3 {{ color: #38bdf8; }}
    code {{ background: #1e293b; padding: 2px 6px; border-radius: 4px; font-family: monospace; color: #34d399; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
    th, td {{ border: 1px solid #334155; padding: 8px 12px; text-align: left; }}
    th {{ background: #1e293b; color: #38bdf8; }}
    a {{ color: #38bdf8; text-decoration: none; }}
  </style>
</head>
<body>
  <p><a href="index.html">← Back to Protocol Hub</a></p>
  <div>{body_html}</div>
</body>
</html>"""


def build_site_documentation(output_dir: Union[str, Path]) -> Path:
    """Build static documentation site for all discovered protocols, AsyncAPI specs, schemas, and manuals."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    catalog = CatalogManager()
    summary = catalog.catalog_summary()

    # Copy docs, schemas, and examples to site output folder if they exist
    root_dir = Path(__file__).resolve().parent.parent.parent
    for folder_name in ["docs", "schemas", "examples"]:
        src_folder = root_dir / folder_name
        if src_folder.exists():
            dest_folder = out / folder_name
            if dest_folder.exists():
                shutil.rmtree(dest_folder)
            shutil.copytree(src_folder, dest_folder, ignore=shutil.ignore_patterns("*.pyc", "__pycache__"))

    index_lines = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <title>OmniUART Universal Protocol Specification & Documentation Hub</title>",
        "  <style>",
        "    body { font-family: system-ui, sans-serif; max-width: 1000px; margin: 2rem auto; background: #0f172a; color: #fff; padding: 0 1rem; line-height: 1.5; }",
        "    h1, h2 { color: #38bdf8; }",
        "    .card { background: #1e293b; padding: 1rem 1.5rem; margin: 1rem 0; border-radius: 8px; border: 1px solid #334155; }",
        "    .tag-badge { background: #0284c7; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: bold; margin-right: 5px; }",
        "    a { color: #34d399; text-decoration: none; font-weight: bold; }",
        "    a:hover { text-decoration: underline; }",
        "    .nav-bar { display: flex; gap: 1rem; background: #1e293b; padding: 1rem; border-radius: 8px; border: 1px solid #334155; margin-bottom: 2rem; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>⚡ OmniUART Hardware Protocol Specification Hub</h1>",
        "  <p>Comprehensive system architecture, AsyncAPI specifications, JSON Schemas, user manuals, and protocol catalog.</p>",
        "  <div class='nav-bar'>",
        "    <a href='#protocols'>📚 Protocol Catalog</a>",
        "    <a href='docs/architecture/system-architecture.md'>🏛️ System Architecture</a>",
        "    <a href='docs/release/guidance.md'>📖 User Manual & CLI Guide</a>",
        "    <a href='schemas/protocol.schema.json'>⚙️ Protocol JSON Schema</a>",
        "    <a href='schemas/script.schema.json'>📜 Script JSON Schema</a>",
        "  </div>",
        "  <h2 id='protocols'>Discovered Hardware Protocols & AsyncAPI Tooling Specifications</h2>",
    ]

    for p in summary["protocols"]:
        spec = catalog.get_protocol(p["filename"])
        if not spec:
            continue
        safe_stem = Path(p["filename"]).stem
        html_filename = f"{safe_stem}.html"
        md_filename = f"{safe_stem}.md"

        (out / html_filename).write_text(generate_html_docs(spec), encoding="utf-8")
        (out / md_filename).write_text(generate_markdown_docs(spec), encoding="utf-8")

        index_lines.append(
            f"  <div class='card'>"
            f"    <h3><span class='tag-badge'>{html.escape(spec.framing.type.value.upper())}</span> {html.escape(spec.metadata.name)} (v{spec.metadata.version})</h3>"
            f"    <p>{html.escape(spec.metadata.description or '')}</p>"
            f"    <p>Baudrate: {spec.serial_config.baudrate} bps | Commands: {len(spec.commands)}</p>"
            f"    <p><a href='{html_filename}'>📄 View HTML Specs</a> | <a href='{md_filename}'>📝 View Markdown</a></p>"
            f"  </div>"
        )

    index_lines.extend(["</body>", "</html>"])
    (out / "index.html").write_text("\n".join(index_lines), encoding="utf-8")

    return out
