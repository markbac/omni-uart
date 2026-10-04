"""Application Services Layer for OmniUART.

Decouples core business logic, catalog queries, session execution, simulation,
fuzzing, replay, documentation and artefact generation from CLI and UI presentation layers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import FrameCodec, validate_fields
from omniuart.core.fuzzer import ProtocolFuzzer
from omniuart.core.models import ProtocolSpec, load_protocol, load_script
from omniuart.core.replayer import SessionReplayer
from omniuart.core.runner import ScriptRunner
from omniuart.core.session import DeviceSession, Exchange, create_transport
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
        protocols = []
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

        scripts = []
        for sf in self.catalog.list_script_files():
            try:
                s = self.catalog._load_script_cached(sf)
                scripts.append({
                    "name": s.name,
                    "filename": sf.name,
                    "protocol": s.protocol,
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

        protocol = cat.get_protocol(script.protocol)
        if protocol is None:
            raise ValueError(f"Protocol '{script.protocol}' declared by script not found.")

        transport = create_transport(protocol, port=port, baudrate=baudrate, virtual=virtual)
        runner = ScriptRunner(script, protocol, transport, read_only=read_only, record_file=record_file)
        results = await runner.run()

        summary = {
            "script": script.name,
            "total_steps": len(results),
            "passed": sum(1 for r in results if r.ok),
            "failed": sum(1 for r in results if not r.ok),
            "results": [
                {
                    "step": r.step_index,
                    "command": r.command_name,
                    "ok": r.ok,
                    "error": r.error,
                }
                for r in results
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
            for spec in cat.protocols.values():
                html = generate_html_docs(spec)
                (out_path / f"{spec.metadata.name}.html").write_text(html, encoding="utf-8")
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
        report = await fuzzer.run_campaign(num_vectors=num_vectors)
        return {
            "protocol": spec.metadata.name,
            "seed": fuzzer.seed,
            "vectors": num_vectors,
            "passed": report.get("passed", 0),
            "failed": report.get("failed", 0),
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
        replayer = SessionReplayer(session_file, speed_multiplier=speed)
        count = await replayer.replay(port=port, baudrate=baudrate, virtual=virtual)
        return {"session_file": session_file, "events_replayed": count}


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
