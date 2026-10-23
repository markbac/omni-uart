"""Application Services Layer for OmniUART (#208, #314, #315).

Decouples core business logic, catalog queries, session execution, simulation,
fuzzing, replay, documentation and artefact generation from CLI and UI presentation layers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import FrameCodec
from omniuart.core.fuzzer import ProtocolFuzzer
from omniuart.core.models import ProtocolSpec
from omniuart.core.recorder import SessionRecorder
from omniuart.core.replayer import SessionReplayer
from omniuart.core.runner import ScriptRunner, StepStatus
from omniuart.core.session import DeviceSession, create_transport
from omniuart.core.transport import AsyncTransport
from omniuart.docs_generator import generate_html_docs
from omniuart.generators import (
    generate_c_header,
    generate_json_schema,
    generate_python_dataclasses,
    generate_wireshark_dissector,
)


class CatalogService:
    """Service for discovering, querying, and loading protocols and scripts."""

    def __init__(self, catalog: Optional[CatalogManager] = None) -> None:
        self.catalog = catalog or CatalogManager()

    def list_catalog(self) -> Dict[str, Any]:
        """Return dict listing all discovered protocols and scripts."""
        protocols: List[Dict[str, Any]] = []
        for pf in self.catalog.list_protocol_files():
            try:
                p = self.catalog._load_protocol_cached(pf)
                protocols.append({
                    "name": p.metadata.name,
                    "version": p.metadata.version,
                    "filename": pf.name,
                    "commands": [c.name for c in p.commands],
                })
            except Exception:
                pass

        scripts: List[Dict[str, Any]] = []
        for sf in self.catalog.list_script_files():
            try:
                s = self.catalog._load_script_cached(sf)
                scripts.append({
                    "name": s.meta.name if s.meta else sf.stem,
                    "filename": sf.name,
                    "protocol": s.meta.protocol if s.meta else "",
                })
            except Exception:
                pass

        return {"protocols": protocols, "scripts": scripts}

    def get_protocol(self, query: str) -> ProtocolSpec:
        """Resolve a protocol by name or file path."""
        p = self.catalog.get_protocol(query)
        if p is None:
            raise ValueError(f"Protocol '{query}' not found in catalog.")
        return p


class CommandExecutionService:
    """Service for formatting, validating, and executing protocol commands."""

    async def execute_command(
        self,
        spec: ProtocolSpec,
        command_name: str,
        params: Dict[str, Any],
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        virtual: bool = False,
        timeout_ms: Optional[int] = None,
        dry_run: bool = False,
        read_only: bool = False,
    ) -> Dict[str, Any]:
        """Validate and send a command, returning exchange results."""
        cmd = spec.get_command(command_name) or spec.get_command_by_id(command_name)
        if cmd is None:
            raise ValueError(f"Unknown command '{command_name}' in protocol '{spec.metadata.name}'.")

        codec = FrameCodec(spec)
        request_bytes = codec.encode_command(cmd, params)

        if dry_run:
            return {
                "dry_run": True,
                "command": cmd.name,
                "request_hex": request_bytes.hex(" "),
                "request_bytes": list(request_bytes),
            }

        transport = create_transport(spec, port=port, baudrate=baudrate, virtual=virtual)
        async with DeviceSession(spec, transport, read_only=read_only) as session:
            exchange = await session.send(cmd, params=params, timeout_ms=timeout_ms)
            return {
                "dry_run": False,
                "command": exchange.command,
                "status": exchange.status.value,
                "latency_ms": exchange.latency_ms,
                "request_hex": exchange.request.hex(" "),
                "response_hex": exchange.response_bytes.hex(" ") if exchange.response_bytes else "",
                "fields": exchange.fields,
                "error": exchange.error,
            }


class AutomationService:
    """Service for executing automation test scripts and sequences."""

    async def run_script(
        self,
        script_query: str,
        catalog: Optional[CatalogManager] = None,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        virtual: bool = False,
        read_only: bool = False,
        record_file: Optional[str] = None,
        report_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        cat = catalog or CatalogManager()
        script = cat.get_script(script_query)
        if script is None:
            raise ValueError(f"Script '{script_query}' not found.")

        protocol_name = script.meta.protocol if script.meta else ""
        protocol = cat.resolve_script_protocol(script) if script else None
        if protocol is None:
            raise ValueError(f"Protocol '{protocol_name}' declared by script not found.")

        transport = create_transport(protocol, port=port, baudrate=baudrate, virtual=virtual)
        recorder = SessionRecorder(protocol_name=protocol.metadata.name) if record_file else None

        async with DeviceSession(protocol, transport, recorder=recorder, read_only=read_only) as session:
            runner = ScriptRunner(script, session)
            result = await runner.run()

        if recorder and record_file:
            recorder.export_jsonl(record_file)
        passed = sum(1 for r in result.steps if r.status == StepStatus.PASSED)
        failed = sum(1 for r in result.steps if r.status != StepStatus.PASSED)
        summary: Dict[str, Any] = {
            "script": script.meta.name if script.meta else script_query,
            "total_steps": len(result.steps),
            "passed": passed,
            "failed": failed,
            "results": [
                {
                    "step": r.index,
                    "command": r.name,
                    "ok": r.status == StepStatus.PASSED,
                    "error": r.message if r.status != StepStatus.PASSED else None,
                }
                for r in result.steps
            ],
        }

        if report_file:
            Path(report_file).write_text(json.dumps(summary, indent=2), encoding="utf-8")

        return summary


class DocumentationService:
    """Service for generating protocol documentation."""

    def generate_documentation(
        self,
        protocol: Optional[str] = None,
        all_protocols: bool = False,
        output_dir: str = "_site",
        catalog: Optional[CatalogManager] = None,
    ) -> Path:
        cat = catalog or CatalogManager()
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        if all_protocols:
            for pf in cat.list_protocol_files():
                try:
                    p_spec = cat._load_protocol_cached(pf)
                    if p_spec is not None:
                        html = generate_html_docs(p_spec)
                        (out_path / f"{p_spec.metadata.name}.html").write_text(html, encoding="utf-8")
                except Exception:
                    pass
            return out_path
        elif protocol:
            spec = cat.get_protocol(protocol)
            if spec is None:
                raise ValueError(f"Protocol '{protocol}' not found.")
            html = generate_html_docs(spec)
            target = out_path / f"{spec.metadata.name}.html"
            target.write_text(html, encoding="utf-8")
            return target
        else:
            raise ValueError("Specify a protocol or set all_protocols=True.")


class FuzzingService:
    """Service for protocol fuzzing and stress testing campaigns."""

    async def run_fuzz_campaign(
        self,
        protocol_query: str,
        num_vectors: int = 20,
        seed: Optional[int] = None,
        catalog: Optional[CatalogManager] = None,
    ) -> Dict[str, Any]:
        cat = catalog or CatalogManager()
        spec = cat.get_protocol(protocol_query)
        if spec is None:
            raise ValueError(f"Protocol '{protocol_query}' not found.")

        fuzzer = ProtocolFuzzer(spec, seed=seed)
        report = await fuzzer.run_campaign(max_vectors=num_vectors)
        return {
            "protocol": spec.metadata.name,
            "seed": fuzzer.seed,
            "vectors": num_vectors,
            "passed": report.outcomes.get("ok", 0),
            "failed": report.outcomes.get("error", 0) + report.outcomes.get("hang", 0) + report.outcomes.get("malformed", 0),
        }


class ReplayService:
    """Service for replaying recorded session logs."""

    async def replay(
        self,
        session_file: str,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        virtual: bool = False,
        speed: float = 1.0,
    ) -> Dict[str, Any]:
        from omniuart.core.transport import HardwareSerialTransport, VirtualTransport
        replay_transport: AsyncTransport
        if port and not virtual:
            replay_transport = HardwareSerialTransport(port=port, baudrate=baudrate or 115200)
        else:
            replay_transport = VirtualTransport(latency_ms=1.0)
        transport = replay_transport
        await transport.open()
        try:
            replayer = SessionReplayer(transport=transport, speed_multiplier=speed)
            count = await replayer.replay_file(session_file)
            return {"session_file": session_file, "events_replayed": count}
        finally:
            await transport.close()


class GeneratorService:
    """Service for generating protocol code, Wireshark dissectors, and schemas."""

    def generate(
        self,
        target: str,
        protocol_query: Optional[str] = None,
        output_file: Optional[str] = None,
        catalog: Optional[CatalogManager] = None,
    ) -> str:
        cat = catalog or CatalogManager()
        if target == "schema":
            result = generate_json_schema()
        else:
            if not protocol_query:
                raise ValueError(f"Target '{target}' requires a protocol name.")
            spec = cat.get_protocol(protocol_query)
            if spec is None:
                raise ValueError(f"Protocol '{protocol_query}' not found.")

            if target == "wireshark":
                result = generate_wireshark_dissector(spec)
            elif target == "c":
                result = generate_c_header(spec)
            elif target == "python":
                result = generate_python_dataclasses(spec)
            else:
                raise ValueError(f"Unknown generation target '{target}'.")

        if output_file:
            Path(output_file).write_text(result, encoding="utf-8")
        return result
