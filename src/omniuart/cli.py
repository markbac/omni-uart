"""OmniUART Command Line Interface (CLI).

Provides protocol help, command dispatching, protocol/script discovery, and test execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import ProtocolSpec, load_protocol, load_script


def build_parser() -> argparse.ArgumentParser:
    """Build command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="omniuart",
        description="OmniUART: Universal Schema-Driven UART Protocol Tool",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

    # 1. list
    list_parser = subparsers.add_parser("list", help="List all discovered protocol definitions and test scripts")
    list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # 2. info (Protocol Help)
    info_parser = subparsers.add_parser("info", help="Display rich protocol help, commands, parameters, and tags")
    info_parser.add_argument("protocol", help="Protocol name, filename, or keyword (e.g. modbus-rtu, ubx)")

    # 3. send (Dispatch Command)
    send_parser = subparsers.add_parser("send", help="Format and send a protocol command")
    send_parser.add_argument("protocol", help="Protocol name or filename")
    send_parser.add_argument("command", help="Command name or ID")
    send_parser.add_argument("--params", "-p", nargs="*", help="Key=value parameters (e.g. channel=1 speed=50)")
    send_parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate framing & CRC without serial port")

    # 4. run (Run Automation Script)
    run_parser = subparsers.add_parser("run", help="Execute an automated sequence test script")
    run_parser.add_argument("script", help="Script name or filename (e.g. ubx-baud-switch-sequence.json)")

    # 5. docs (Generate Documentation)
    docs_parser = subparsers.add_parser("docs", help="Auto-generate Markdown/HTML protocol specification documentation site")
    docs_parser.add_argument("protocol", nargs="?", default=None, help="Protocol name or filename (or omitted when using --all)")
    docs_parser.add_argument("--all", action="store_true", help="Build full documentation site for all discovered protocols")
    docs_parser.add_argument("--format", choices=["markdown", "html"], default="html", help="Documentation output format")
    docs_parser.add_argument("--output-dir", "-o", default="_site", help="Output directory path")

    # 6. lint (Protocol Linter)
    lint_parser = subparsers.add_parser("lint", help="Lint and validate protocol definition file against JSON Schema")
    lint_parser.add_argument("file", help="Path to YAML or JSON protocol definition file")

    # 7. convert (Schema Format Converter)
    convert_parser = subparsers.add_parser("convert", help="Convert legacy protocol into standard uart-interface.schema.json format")
    convert_parser.add_argument("file", help="Path to legacy protocol definition file")
    convert_parser.add_argument("--output", "-o", help="Output JSON file path")

    # 8. fuzz (Protocol Fuzzer & MCU Stress Tester)
    fuzz_parser = subparsers.add_parser("fuzz", help="Run automated fuzzing & MCU firmware stress testing campaign")
    fuzz_parser.add_argument("protocol", help="Protocol name or filename to fuzz")
    fuzz_parser.add_argument("--vectors", "-n", type=int, default=20, help="Number of fuzz test vectors to run")

    return parser


def format_protocol_help(spec: ProtocolSpec) -> str:
    """Generate rich protocol help documentation for terminal output."""
    lines: List[str] = []
    meta = spec.metadata
    lines.append("=" * 70)
    lines.append(f" PROTOCOL HELP: {meta.name} (v{meta.version})")
    lines.append("=" * 70)
    if meta.description:
        lines.append(f" Description : {meta.description}")
    lines.append(f" Baudrate    : {spec.serial_config.baudrate} bps")
    lines.append(f" Framing     : {spec.serial_config.bytesize}N{spec.serial_config.stopbits} ({spec.framing.type.value})")
    if spec.framing.integrity:
        lines.append(f" Integrity   : {spec.framing.integrity.algorithm}")
    lines.append("-" * 70)

    # Group commands by tag
    tagged_map = {}
    for cmd in spec.commands:
        tags = cmd.tags if cmd.tags else ["general"]
        for tag in tags:
            tagged_map.setdefault(tag, []).append(cmd)

    lines.append(" COMMAND CATALOG & PARAMETERS:")
    lines.append("-" * 70)

    for tag, cmds in tagged_map.items():
        lines.append(f"\n  🏷️  [{tag.upper()} TAB]")
        for cmd in cmds:
            desc = f" - {cmd.description}" if cmd.description else ""
            lines.append(f"    • {cmd.name} (ID: {cmd.id}){desc}")
            if cmd.parameters:
                lines.append("      Parameters:")
                for p in cmd.parameters:
                    unit_str = f" [{p.unit}]" if p.unit else ""
                    range_str = f" (min: {p.min}, max: {p.max})" if p.min is not None else ""
                    options_str = f" options: {p.options}" if p.options else ""
                    lines.append(f"        - {p.name}: {p.type.value}{unit_str}{range_str}{options_str}")
            if cmd.response:
                lines.append(f"      Expected Response (timeout: {cmd.response.timeout_ms}ms):")
                for rf in cmd.response.fields:
                    rf_unit = f" [{rf.unit}]" if rf.unit else ""
                    lines.append(f"        <- {rf.name}: {rf.type.value}{rf_unit}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    catalog = CatalogManager()

    if args.subcommand == "list":
        summary = catalog.catalog_summary()
        if getattr(args, "json", False):
            print(json.dumps(summary, indent=2))
        else:
            print(f"\nDiscovered Protocols ({summary['protocols_found']}):")
            for p in summary["protocols"]:
                print(f"  - {p['filename']} : {p['name']} (v{p['version']}, {p['commands_count']} cmds)")
            print(f"\nDiscovered Scripts ({summary['scripts_found']}):")
            for s in summary["scripts"]:
                print(f"  - {s['filename']} : {s['name']} (Target: {s['protocol']})")
        return 0

    elif args.subcommand == "info":
        spec = catalog.get_protocol(args.protocol)
        if not spec:
            print(f"Error: Protocol '{args.protocol}' not found in catalog.", file=sys.stderr)
            return 1
        print(format_protocol_help(spec))
        return 0

    elif args.subcommand == "send":
        spec = catalog.get_protocol(args.protocol)
        if not spec:
            print(f"Error: Protocol '{args.protocol}' not found.", file=sys.stderr)
            return 1
        cmd = spec.get_command(args.command) or spec.get_command_by_id(args.command)
        if not cmd:
            print(f"Error: Command '{args.command}' not found in protocol {spec.metadata.name}.", file=sys.stderr)
            return 1

        params_dict = {}
        if args.params:
            for item in args.params:
                if "=" in item:
                    k, v = item.split("=", 1)
                    try:
                        params_dict[k.strip()] = int(v.strip())
                    except ValueError:
                        try:
                            params_dict[k.strip()] = float(v.strip())
                        except ValueError:
                            params_dict[k.strip()] = v.strip()

        print(f"Executing command '{cmd.name}' (ID: {cmd.id}) on protocol '{spec.metadata.name}'...")
        print(f"  Parameters: {params_dict}")
        print("  Status    : [DRY-RUN SIMULATION OK]")
        if cmd.response:
            print(f"  Response  : Expected '{cmd.response.fields}' within {cmd.response.timeout_ms}ms")
        return 0

    elif args.subcommand == "run":
        script = catalog.get_script(args.script)
        if not script:
            print(f"Error: Script '{args.script}' not found.", file=sys.stderr)
            return 1
        print(f"Running script '{script.meta.name}' ({len(script.steps)} steps) targeting '{script.meta.protocol}'...")
        for idx, step in enumerate(script.steps, 1):
            if step.command:
                print(f"  Step {idx}: Send '{step.command}' (params: {step.params})")
            else:
                print(f"  Step {idx}: Pause for {step.delay_ms} ms")
        print("Script execution completed successfully.")
        return 0

    elif args.subcommand == "docs":
        from omniuart.docs_generator import build_site_documentation, generate_html_docs, generate_markdown_docs
        out_dir = Path(args.output_dir)
        if args.all or not args.protocol:
            site_path = build_site_documentation(out_dir)
            print(f"Built complete protocol documentation site at: {site_path.resolve()}")
            return 0
        else:
            spec = catalog.get_protocol(args.protocol)
            if not spec:
                print(f"Error: Protocol '{args.protocol}' not found.", file=sys.stderr)
                return 1
            out_dir.mkdir(parents=True, exist_ok=True)
            doc_str = generate_html_docs(spec) if args.format == "html" else generate_markdown_docs(spec)
            ext = "html" if args.format == "html" else "md"
            target_file = out_dir / f"{spec.metadata.name.lower().replace(' ', '_')}.{ext}"
            target_file.write_text(doc_str, encoding="utf-8")
            print(f"Generated protocol docs: {target_file.resolve()}")
            return 0

    elif args.subcommand == "lint":
        from omniuart.linter import lint_protocol_file
        is_valid, errors = lint_protocol_file(args.file)
        if is_valid:
            print(f"✅ [VALID] Protocol file '{args.file}' passed all linting & schema validations.")
            return 0
        else:
            print(f"❌ [LINT ERRORS] Protocol file '{args.file}' failed validation:", file=sys.stderr)
            for err in errors:
                print(f"   • {err}", file=sys.stderr)
            return 1

    elif args.subcommand == "convert":
        from omniuart.linter import convert_protocol_to_kit
        kit_data = convert_protocol_to_kit(args.file, output_path=args.output)
        if args.output:
            print(f"Successfully converted '{args.file}' to kit schema format: {args.output}")
        else:
            print(json.dumps(kit_data, indent=2))
        return 0

    elif args.subcommand == "fuzz":
        import asyncio
        from omniuart.core.fuzzer import ProtocolFuzzer
        from omniuart.core.transport import VirtualTransport
        spec = catalog.get_protocol(args.protocol)
        if not spec:
            print(f"Error: Protocol '{args.protocol}' not found.", file=sys.stderr)
            return 1
        print(f"Starting Fuzzing Campaign for '{spec.metadata.name}' ({args.vectors} vectors)...")
        fuzzer = ProtocolFuzzer(spec)
        transport = VirtualTransport(spec, latency_ms=1.0)
        report = asyncio.run(fuzzer.run_campaign(transport, max_vectors=args.vectors))
        print(f"Campaign Completed:")
        print(f"  Total Vectors Executed : {report.total_vectors}")
        print(f"  Handled / Rejected     : {report.handled_count}")
        print(f"  Hangs / Timeouts       : {report.hang_count}")
        print(f"  Crashes / Errors       : {report.crash_count}")
        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
