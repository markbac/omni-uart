"""Automated Protocol Specification Documentation & MkDocs Site Generator for OmniUART."""

from __future__ import annotations

import html
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Union

from omniuart.core.asyncapi_exporter import export_asyncapi_yaml
from omniuart.core.catalog import CatalogManager
from omniuart.core.models import ProtocolSpec, load_protocol


def generate_markdown_docs(spec: ProtocolSpec, safe_stem: Optional[str] = None) -> str:
    """Generate Markdown specification document for a protocol including AsyncAPI 2.6.0 spec."""
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
    if safe_stem:
        lines.append(f"> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/{safe_stem}.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/{safe_stem}.html)")
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

    lines.append("## Formal AsyncAPI 2.6.0 Specification\n")
    lines.append("```yaml")
    lines.append(export_asyncapi_yaml(spec))
    lines.append("```\n")

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


def _compile_asyncapi_html(yaml_path: Path, html_path: Path, root_dir: Path, asyncapi_docs_dir: Path, safe_stem: str) -> None:
    """Helper to compile standalone AsyncAPI HTML page via @asyncapi/cli."""
    try:
        tmp_out_dir = asyncapi_docs_dir / f"tmp_{safe_stem}"
        tmp_out_dir.mkdir(exist_ok=True)
        res = subprocess.run(
            ["npx.cmd" if os.name == "nt" else "npx", "asyncapi", "generate", "fromTemplate", str(yaml_path), "@asyncapi/html-template", "-o", str(tmp_out_dir), "--param", "singleFile=true", "--force-write"],
            cwd=str(root_dir),
            capture_output=True,
            text=True,
        )
        generated_index = tmp_out_dir / "index.html"
        if generated_index.exists():
            shutil.copy2(generated_index, html_path)
        shutil.rmtree(tmp_out_dir, ignore_errors=True)
    except Exception:
        pass


def build_site_documentation(output_dir: Union[str, Path]) -> Path:
    """Build static documentation site for all discovered protocols, AsyncAPI specs, schemas, and manuals."""
    from concurrent.futures import ThreadPoolExecutor

    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    root_dir = Path(__file__).resolve().parent.parent.parent
    docs_dir = root_dir / "docs"
    protocols_docs_dir = docs_dir / "protocols"
    asyncapi_docs_dir = protocols_docs_dir / "asyncapi"
    protocols_docs_dir.mkdir(parents=True, exist_ok=True)
    asyncapi_docs_dir.mkdir(parents=True, exist_ok=True)

    catalog = CatalogManager()
    summary = catalog.catalog_summary()

    protocol_nav_index = [
        "# Discovered Hardware Protocols & AsyncAPI Specifications\n",
        "Below is the complete catalog of auto-discovered hardware UART protocols with detailed parameters, command signatures, and formal AsyncAPI 2.6.0 specifications.\n",
    ]

    html_tasks = []

    for p in summary["protocols"]:
        spec = catalog.get_protocol(p["filename"])
        if not spec:
            continue
        safe_stem = Path(p["filename"]).stem
        md_path = protocols_docs_dir / f"{safe_stem}.md"
        yaml_path = asyncapi_docs_dir / f"{safe_stem}.yaml"
        html_path = asyncapi_docs_dir / f"{safe_stem}.html"

        # Write Markdown & AsyncAPI YAML specs
        yaml_content = export_asyncapi_yaml(spec)
        yaml_path.write_text(yaml_content, encoding="utf-8")
        md_path.write_text(generate_markdown_docs(spec, safe_stem=safe_stem), encoding="utf-8")

        html_tasks.append((yaml_path, html_path, root_dir, asyncapi_docs_dir, safe_stem))

        protocol_nav_index.append(
            f"### [{spec.metadata.name}]({safe_stem}.md) (v{spec.metadata.version})\n"
            f"- **Description**: {spec.metadata.description or 'N/A'}\n"
            f"- **Framing**: `{spec.framing.type.value.upper()}` | **Baudrate**: `{spec.serial_config.baudrate} bps` | **Commands**: `{len(spec.commands)}`\n"
            f"- **AsyncAPI**: [YAML Spec](asyncapi/{safe_stem}.yaml) | [Interactive HTML Viewer](asyncapi/{safe_stem}.html)\n"
        )

    # Parallelize AsyncAPI HTML compilation across worker threads
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(_compile_asyncapi_html, *task) for task in html_tasks]
        for f in futures:
            f.result()

    (protocols_docs_dir / "index.md").write_text("\n".join(protocol_nav_index), encoding="utf-8")

    # Try building with MkDocs if mkdocs is available
    mkdocs_yml = root_dir / "mkdocs.yml"
    if mkdocs_yml.exists():
        try:
            res = subprocess.run(
                ["mkdocs", "build", "-d", str(out)],
                cwd=str(root_dir),
                capture_output=True,
                text=True,
            )
            if res.returncode == 0:
                return out
        except Exception:
            pass

    # Fallback HTML index generator
    index_lines = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <title>OmniUART Hardware Protocol Specification Hub</title>",
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
        (out / md_filename).write_text(generate_markdown_docs(spec, safe_stem=safe_stem), encoding="utf-8")

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
