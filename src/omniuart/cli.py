"""OmniUART Command Line Interface (CLI).

Provides protocol help, command dispatching, protocol/script discovery, and test execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import CommandSafety, CommandSpec, ProtocolSpec, load_protocol, load_script

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def build_parser() -> argparse.ArgumentParser:
    """Build command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="omniuart",
        description="OmniUART: Universal Schema-Driven UART Protocol Tool",
    )
    parser.add_argument("--log-file", help="Custom log file path (default: ~/.omniuart/logs/omniuart.log)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Log verbosity level")
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
    send_parser.add_argument("--port", "-P", help="Serial port to transmit on (e.g. COM3, /dev/ttyUSB0, or a PySerial URL such as loop://)")
    send_parser.add_argument("--baudrate", "-b", type=int, help="Baud rate override (default: from the protocol)")
    send_parser.add_argument("--virtual", action="store_true", help="Transmit to the built-in simulated device instead of a serial port")
    send_parser.add_argument("--timeout", type=int, help="Response timeout in milliseconds (default: from the protocol)")
    send_parser.add_argument("--dry-run", action="store_true", help="Only build and print the frame; transmit nothing")
    send_parser.add_argument("--read-only", action="store_true", help="Refuse any command not marked safety: read_only")
    send_parser.add_argument("--yes", "-y", action="store_true", help="Confirm sending a destructive command")

    # 4. run (Run Automation Script)
    run_parser = subparsers.add_parser("run", help="Execute an automated sequence test script")
    run_parser.add_argument("script", help="Script name, filename or path (e.g. ubx-baud-switch-sequence.json)")
    run_parser.add_argument("--port", "-P", help="Serial port to run against (e.g. COM3, /dev/ttyUSB0, or a PySerial URL such as loop://)")
    run_parser.add_argument("--baudrate", "-b", type=int, help="Baud rate override (default: from the protocol)")
    run_parser.add_argument("--virtual", action="store_true", help="Run against the built-in simulated device instead of a serial port")
    run_parser.add_argument("--protocol", help="Protocol name or file to use instead of the one named in the script")
    run_parser.add_argument("--read-only", action="store_true", help="Refuse any step whose command is not marked safety: read_only")
    run_parser.add_argument("--record", help="Write every transmitted and received frame to this .jsonl file")
    run_parser.add_argument("--report", help="Write a machine-readable JSON result report to this file")

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
    fuzz_parser.add_argument("--seed", type=int, default=None, help="Seed for reproducible random mutations (printed in the summary)")

    # 9. replay (Session Replay Engine)
    replay_parser = subparsers.add_parser("replay", help="Replay recorded session transactions onto a serial transport")
    replay_parser.add_argument("session_file", help="Path to recorded .jsonl session file")
    replay_parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier (default: 1.0)")

    # 10. ui (Interactive Dynamic UI Launcher)
    ui_parser = subparsers.add_parser("ui", help="Launch interactive UI application")
    ui_parser.add_argument("--host", default="127.0.0.1", help="UI server bind host (default: 127.0.0.1)")
    ui_parser.add_argument("--port", type=int, default=8000, help="UI server bind port (default: 8000)")
    ui_parser.add_argument("--mode", choices=["desktop", "web"], default="desktop", help="UI display mode: 'desktop' (native window) or 'web' (browser tab)")
    ui_parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser in web mode")

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

    if not spec.commands:
        lines.append("  (no host-to-device commands defined)")

    if spec.telemetry:
        lines.append("\n DEVICE-INITIATED MESSAGES:")
        lines.append("-" * 70)
        for msg in spec.telemetry:
            desc = f" - {msg.description}" if msg.description else ""
            lines.append(f"    • {msg.name} (ID: {msg.id}){desc}")
            for f in msg.fields:
                f_unit = f" [{f.unit}]" if f.unit else ""
                lines.append(f"        <- {f.name}: {f.type.value}{f_unit}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def _send_command(spec: ProtocolSpec, cmd: CommandSpec, params: Dict[str, Any], args: argparse.Namespace) -> int:
    """Encode, transmit and report one command. Exit codes: 0 ok, 1 no valid response, 2 bad input, 3 transport error."""
    import asyncio

    from omniuart.core.codec import CodecError, FrameCodec
    from omniuart.core.session import DeviceSession, ExchangeStatus, create_transport

    print(f"Command '{cmd.name}' (ID: {cmd.id}) on protocol '{spec.metadata.name}'")
    try:
        frame = FrameCodec(spec).encode_command(cmd, params)
    except CodecError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"  Request   : {frame.hex(' ').upper()} ({len(frame)} bytes)")

    if args.read_only and not cmd.is_read_only:
        print(f"Error: read-only mode: '{cmd.name}' is {cmd.safety.value}, only read_only commands may be sent.", file=sys.stderr)
        return 2
    if cmd.safety is CommandSafety.DESTRUCTIVE and not args.dry_run and not args.yes:
        print(f"Error: '{cmd.name}' is marked destructive. Repeat with --yes to send it.", file=sys.stderr)
        return 2

    if args.dry_run:
        print("  Status    : DRY-RUN (nothing transmitted)")
        return 0
    try:
        transport = create_transport(spec, port=args.port, baudrate=args.baudrate, virtual=args.virtual)
    except ValueError as exc:
        print(f"Error: {exc}. Use --port <port>, --virtual, or --dry-run.", file=sys.stderr)
        return 2

    async def _run():
        async with DeviceSession(spec, transport, read_only=args.read_only) as session:
            return await session.send(cmd, params, timeout_ms=args.timeout)

    try:
        exchange = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 - opening the port failed
        print(f"Error: cannot use transport: {exc}", file=sys.stderr)
        return 3

    if exchange.status is ExchangeStatus.TRANSPORT_ERROR:
        print(f"  Status    : TRANSPORT ERROR - {exchange.error}", file=sys.stderr)
        return 3
    if exchange.response_bytes:
        print(f"  Response  : {exchange.response_bytes.hex(' ').upper()} ({len(exchange.response_bytes)} bytes, {exchange.latency_ms:.1f} ms)")
    if not exchange.ok:
        print(f"  Status    : FAILED - {exchange.error}", file=sys.stderr)
        return 1
    if exchange.response is None:
        print("  Status    : SENT (command defines no response)")
        return 0
    for name, value in exchange.fields.items():
        print(f"    {name} = {value}")
    print("  Status    : OK")
    return 0


def _resolve_script_protocol(script: Any, catalog: CatalogManager, override: Optional[str]) -> Optional[ProtocolSpec]:
    """Find the protocol a script targets (shared with the desktop GUI)."""
    return catalog.resolve_script_protocol(script, override)


def _run_script(args: argparse.Namespace, catalog: CatalogManager) -> int:
    """Execute a script against a real or simulated device. Exit codes follow ScriptResult.exit_code."""
    import asyncio

    from omniuart.core.codec import CodecError
    from omniuart.core.recorder import SessionRecorder
    from omniuart.core.runner import EXIT_FAILED, EXIT_INVALID, EXIT_TRANSPORT, ScriptRunner, StepStatus
    from omniuart.core.session import DeviceSession, create_transport

    script_path = Path(args.script)
    try:
        script = load_script(script_path) if script_path.is_file() else catalog.get_script(args.script)
    except Exception as exc:  # noqa: BLE001 - malformed script file
        print(f"Error: cannot load script '{args.script}': {exc}", file=sys.stderr)
        return EXIT_INVALID
    if not script:
        print(f"Error: Script '{args.script}' not found.", file=sys.stderr)
        return 1
    spec = _resolve_script_protocol(script, catalog, args.protocol)
    if spec is None:
        print(f"Error: protocol '{args.protocol or script.meta.protocol}' for this script was not found. Use --protocol.", file=sys.stderr)
        return EXIT_INVALID
    try:
        transport = create_transport(spec, port=args.port, baudrate=args.baudrate, virtual=args.virtual)
        recorder = SessionRecorder() if args.record else None
        session = DeviceSession(spec, transport, recorder=recorder, read_only=args.read_only)
    except CodecError as exc:
        print(f"Error: cannot use protocol '{spec.metadata.name}': {exc}", file=sys.stderr)
        return EXIT_INVALID
    except ValueError as exc:
        print(f"Error: {exc}. Use --port <port> or --virtual.", file=sys.stderr)
        return EXIT_INVALID

    symbols = {StepStatus.PASSED: "PASS", StepStatus.FAILED: "FAIL", StepStatus.ERROR: "ERROR", StepStatus.SKIPPED: "SKIP"}

    def show(step: Any) -> None:
        print(f"  [{symbols[step.status]}] {step.index}. {step.name} ({step.duration_ms:.0f} ms)")
        if step.message and step.status is not StepStatus.PASSED:
            print(f"         {step.message}")

    print(f"Running script '{script.meta.name}' ({len(script.steps)} steps) on protocol '{spec.metadata.name}'...")

    async def _go():
        try:
            await session.open()
        except Exception as exc:  # noqa: BLE001 - the port could not be opened
            return exc
        try:
            return await ScriptRunner(script, session, on_step=show, on_log=lambda m: print(f"         log: {m}")).run()
        finally:
            await session.close()

    result = asyncio.run(_go())
    if isinstance(result, Exception):
        print(f"Error: cannot use transport: {result}", file=sys.stderr)
        return EXIT_TRANSPORT

    if recorder:
        recorder.export_jsonl(args.record)
    if args.report:
        Path(args.report).write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
    counts = {status: sum(1 for s in result.steps if s.status is status) for status in StepStatus}
    print(f"Result: {'PASSED' if result.passed else 'FAILED'} - {counts[StepStatus.PASSED]} passed, {counts[StepStatus.FAILED]} failed, "
          f"{counts[StepStatus.ERROR]} errors, {counts[StepStatus.SKIPPED]} skipped")
    return result.exit_code if result.steps else EXIT_FAILED


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    from omniuart.core.logger import setup_logging

    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(log_file=getattr(args, "log_file", None), log_level=getattr(args, "log_level", "INFO"))

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
        for item in args.params or []:
            if "=" not in item:
                print(f"Error: parameter '{item}' must be written key=value.", file=sys.stderr)
                return 2
            key, value = item.split("=", 1)
            params_dict[key.strip()] = value.strip()

        return _send_command(spec, cmd, params_dict, args)

    elif args.subcommand == "run":
        return _run_script(args, catalog)

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
        from omniuart.core.codec import CodecError
        from omniuart.core.fuzzer import ProtocolFuzzer
        from omniuart.core.transport import VirtualTransport
        spec = catalog.get_protocol(args.protocol)
        if not spec:
            print(f"Error: Protocol '{args.protocol}' not found.", file=sys.stderr)
            return 1
        print(f"Starting Fuzzing Campaign for '{spec.metadata.name}' ({args.vectors} vectors)...")
        try:
            fuzzer = ProtocolFuzzer(spec, seed=args.seed)
            transport = VirtualTransport(spec, latency_ms=1.0)
            report = asyncio.run(fuzzer.run_campaign(transport, max_vectors=args.vectors))
        except CodecError as exc:
            print(f"Error: cannot fuzz '{spec.metadata.name}': {exc}", file=sys.stderr)
            return 1
        print("Campaign Completed:")
        print(f"  Seed                   : {report.seed if report.seed is not None else 'random'}")
        print(f"  Total Vectors Executed : {report.total_vectors}")
        print(f"  Handled correctly      : {report.handled_count}")
        print(f"  Unexpectedly accepted  : {report.unexpected_count}")
        print(f"  Malformed responses    : {report.malformed_count}")
        print(f"  Hangs / Timeouts       : {report.hang_count}")
        print(f"  Transport errors       : {report.crash_count}")
        return 0 if report.passed else 1

    elif args.subcommand == "replay":
        import asyncio
        from omniuart.core.replayer import SessionReplayer
        from omniuart.core.transport import VirtualTransport
        print(f"Replaying session file: {args.session_file} (speed: {args.speed}x)...")
        transport = VirtualTransport(latency_ms=1.0)
        replayer = SessionReplayer(transport, speed_multiplier=args.speed)
        count = asyncio.run(replayer.replay_file(args.session_file))
    elif args.subcommand == "ui":
        return launch_ui_server(host=args.host, port=args.port, open_browser=not args.no_browser, mode=args.mode)

    else:
        # Default behavior when launched with no subcommand (e.g. double-clicking standalone EXE)
        print("No subcommand specified. Launching OmniUART Desktop App Window...")
        return launch_ui_server(host="127.0.0.1", port=8000, open_browser=True, mode="desktop")


def launch_ui_server(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True, mode: str = "desktop") -> int:
    """Launch local Uvicorn FastAPI server and open Desktop App window or browser tab."""
    import threading
    import uvicorn

    if mode == "desktop":
        from omniuart.core.runner import EXIT_INVALID
        from omniuart.ui.desktop import TKINTER_MISSING_MESSAGE, launch_desktop_window, tkinter_available

        if not tkinter_available():
            print(f"Error: {TKINTER_MISSING_MESSAGE}", file=sys.stderr)
            return EXIT_INVALID

    # Enforce loopback host safety for security (#131)
    if not host or host in ("0.0.0.0", "::"):
        host = "127.0.0.1"

    url = f"http://{host}:{port}"
    print(f"\n========================================================")
    print(f"  ⚡ OmniUART Interactive Control Workbench ({mode.upper()} Mode)")
    print(f"  URL: {url}")
    print(f"========================================================\n")

    if mode == "desktop":
        threading.Timer(1.2, lambda: launch_desktop_window(url)).start()
    elif open_browser:
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    from omniuart.ui.app import app
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0





if __name__ == "__main__":
    sys.exit(main())
