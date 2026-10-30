"""Application Services Layer for OmniUART (#208, #314, #315).

The CLI and the web API call these services for catalog lookups, sending commands, running scripts,
documentation, fuzzing, replay and code generation. The services hold the shared rules (lookup,
safety checks, transport selection) and return structured results; the front ends only present
them and turn a :class:`ServiceError` into an exit code or an HTTP status.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Collection, Dict, List, Mapping, Optional, Tuple

from omniuart.core.catalog import CatalogError, CatalogManager
from omniuart.core.codec import CodecError, FrameCodec
from omniuart.core.fuzzer import FuzzReport, ProtocolFuzzer
from omniuart.core.models import CommandSafety, CommandSpec, ProtocolSpec, ScriptSpec, load_script
from omniuart.core.recorder import SessionRecorder
from omniuart.core.replayer import ReplayResult, SessionReplayer
from omniuart.core.runner import ScriptResult, ScriptRunner, StepResult
from omniuart.core.session import CommandBlockedError, DeviceSession, Exchange, SerialSession, create_transport
from omniuart.core.transport import AsyncTransport, HardwareSerialTransport, VirtualTransport

logger = logging.getLogger(__name__)


class ErrorKind(str, Enum):
    """Why a service call could not be carried out. Front ends map each kind to an exit code or HTTP status."""

    NOT_FOUND = "not_found"  # unknown protocol, command, script or file
    INVALID = "invalid"  # bad parameters, unloadable definition, impossible option combination
    BLOCKED = "blocked"  # refused by a read-only session
    CONFIRMATION_REQUIRED = "confirmation_required"  # the command needs an explicit yes
    TRANSPORT = "transport"  # the port could not be opened or the link failed


class ServiceError(Exception):
    """A service call that could not be carried out; ``kind`` says why."""

    def __init__(self, message: str, kind: ErrorKind) -> None:
        super().__init__(message)
        self.kind = kind


# Commands the CLI asks to confirm with --yes; the web and desktop front ends confirm every command that changes state.
CLI_CONFIRM = frozenset({CommandSafety.DESTRUCTIVE})
UI_CONFIRM = frozenset({CommandSafety.MUTATING, CommandSafety.DESTRUCTIVE})


def check_command_allowed(
    cmd: CommandSpec,
    read_only: bool,
    confirmed: bool,
    confirm_levels: Collection[CommandSafety] = UI_CONFIRM,
) -> None:
    """Raise :class:`ServiceError` if ``cmd`` may not be sent: refused by a read-only session, or not yet confirmed."""
    if read_only and not cmd.is_read_only:
        raise ServiceError(
            f"read-only mode: '{cmd.name}' is {cmd.safety.value}, only read_only commands may be sent", ErrorKind.BLOCKED
        )
    if cmd.safety in confirm_levels and not confirmed:
        raise ServiceError(f"'{cmd.name}' is {cmd.safety.value}: it must be confirmed before it is sent", ErrorKind.CONFIRMATION_REQUIRED)


class TransportSelectionError(ServiceError):
    """No transport, or both a port and the virtual device, was chosen."""

    def __init__(self, message: str) -> None:
        super().__init__(message, ErrorKind.INVALID)


def _transport(spec: ProtocolSpec, port: Optional[str], baudrate: Optional[int], virtual: bool) -> AsyncTransport:
    try:
        return create_transport(spec, port=port, baudrate=baudrate, virtual=virtual)
    except ValueError as exc:
        raise TransportSelectionError(str(exc)) from exc


class CatalogService:
    """Service for discovering, querying, and loading protocols and scripts."""

    def __init__(self, catalog: Optional[CatalogManager] = None) -> None:
        self.catalog = catalog or CatalogManager()

    def summary(self) -> Dict[str, Any]:
        """Protocols, scripts, files that failed to load, and name collisions."""
        return self.catalog.catalog_summary()

    def get_protocol(self, query: str, first: bool = False) -> ProtocolSpec:
        """Resolve a protocol by file name, title or partial name."""
        try:
            spec = self.catalog.get_protocol(query, first=first)
        except CatalogError as exc:
            raise ServiceError(str(exc), ErrorKind.INVALID) from exc
        if spec is None:
            raise ServiceError(f"Protocol '{query}' not found.", ErrorKind.NOT_FOUND)
        return spec

    def get_command(self, spec: ProtocolSpec, name_or_id: str) -> CommandSpec:
        cmd = spec.get_command(name_or_id) or spec.get_command_by_id(name_or_id)
        if cmd is None:
            raise ServiceError(f"Command '{name_or_id}' not found in protocol {spec.metadata.name}.", ErrorKind.NOT_FOUND)
        return cmd

    def get_script(self, ref: str, allow_path: bool = True) -> ScriptSpec:
        """Load a script from a file path (when ``allow_path``) or find it in the catalog."""
        try:
            script = load_script(Path(ref)) if allow_path and Path(ref).is_file() else self.catalog.get_script(ref)
        except Exception as exc:  # noqa: BLE001 - a malformed script file is reported, not raised raw
            raise ServiceError(f"cannot load script '{ref}': {exc}", ErrorKind.INVALID) from exc
        if script is None:
            raise ServiceError(f"Script '{ref}' not found.", ErrorKind.NOT_FOUND)
        return script

    def script_protocol(self, script: ScriptSpec, override: Optional[str] = None) -> ProtocolSpec:
        """The protocol a script targets: ``override``, else the one the script names."""
        try:
            spec = self.catalog.resolve_script_protocol(script, override)
        except CatalogError as exc:
            raise ServiceError(str(exc), ErrorKind.INVALID) from exc
        if spec is None:
            raise ServiceError(f"protocol '{override or script.meta.protocol}' for this script was not found", ErrorKind.INVALID)
        return spec


@dataclass
class SendResult:
    """One command: the encoded request and, unless it was a dry run, what happened on the link."""

    command: CommandSpec
    request: bytes
    exchange: Optional[Exchange] = None


class CommandExecutionService:
    """Service for validating, confirming and sending protocol commands."""

    def __init__(self, catalog: Optional[CatalogService] = None) -> None:
        self.catalog = catalog or CatalogService()

    def execute(
        self,
        spec: ProtocolSpec,
        command: str,
        params: Mapping[str, Any],
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        virtual: bool = False,
        timeout_ms: Optional[int] = None,
        dry_run: bool = False,
        read_only: bool = False,
        confirmed: bool = False,
        confirm_levels: Collection[CommandSafety] = CLI_CONFIRM,
        record_file: Optional[str] = None,
    ) -> SendResult:
        """Encode ``command`` and, unless ``dry_run``, send it over a new link and wait for the response.

        A failure on the link after it opened is reported in ``exchange.status``, not raised.
        """
        cmd = self.catalog.get_command(spec, command)
        try:
            request = FrameCodec(spec).encode_command(cmd, params)
        except CodecError as exc:
            raise ServiceError(str(exc), ErrorKind.INVALID) from exc
        check_command_allowed(cmd, read_only, confirmed or dry_run, confirm_levels)
        if dry_run:
            return SendResult(cmd, request)

        transport = _transport(spec, port, baudrate, virtual)
        recorder = SessionRecorder(protocol_name=spec.metadata.name) if record_file else None

        async def run() -> Exchange:
            async with DeviceSession(spec, transport, recorder=recorder, read_only=read_only) as session:
                return await session.send(cmd, params, timeout_ms=timeout_ms)

        try:
            exchange = asyncio.run(run())
        except Exception as exc:  # noqa: BLE001 - opening the port failed
            raise ServiceError(f"cannot use transport: {exc}", ErrorKind.TRANSPORT) from exc
        if recorder and record_file:
            recorder.export_jsonl(record_file)
        return SendResult(cmd, request, exchange)

    async def send_on(
        self,
        session: SerialSession,
        cmd: CommandSpec,
        params: Mapping[str, Any],
        confirmed: bool = False,
        confirm_levels: Collection[CommandSafety] = UI_CONFIRM,
    ) -> Exchange:
        """Send ``cmd`` on an already open session (the web API's shared link)."""
        check_command_allowed(cmd, session.read_only, confirmed, confirm_levels)
        try:
            return await session.send(cmd, params)
        except CodecError as exc:
            raise ServiceError(str(exc), ErrorKind.INVALID) from exc
        except CommandBlockedError as exc:
            raise ServiceError(str(exc), ErrorKind.BLOCKED) from exc


@dataclass
class ScriptOutcome:
    """A finished script run."""

    script: ScriptSpec
    protocol: ProtocolSpec
    result: ScriptResult


class AutomationService:
    """Service for executing automation test scripts and sequences."""

    def __init__(self, catalog: Optional[CatalogService] = None) -> None:
        self.catalog = catalog or CatalogService()

    def prepare(
        self, script_ref: str, protocol: Optional[str] = None, allow_path: bool = True
    ) -> Tuple[ScriptSpec, ProtocolSpec]:
        """Load the script and its protocol without running anything."""
        script = self.catalog.get_script(script_ref, allow_path=allow_path)
        return script, self.catalog.script_protocol(script, protocol)

    def run(
        self,
        script_ref: str,
        protocol: Optional[str] = None,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        virtual: bool = False,
        read_only: bool = False,
        record_file: Optional[str] = None,
        report_file: Optional[str] = None,
        on_start: Optional[Callable[[ScriptSpec, ProtocolSpec], None]] = None,
        on_step: Optional[Callable[[StepResult], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> ScriptOutcome:
        """Run a script against a real port or the simulated device."""
        script, spec = self.prepare(script_ref, protocol)
        try:
            transport = _transport(spec, port, baudrate, virtual)
            recorder = SessionRecorder(protocol_name=spec.metadata.name) if record_file else None
            session = DeviceSession(spec, transport, recorder=recorder, read_only=read_only)
        except CodecError as exc:
            raise ServiceError(f"cannot use protocol '{spec.metadata.name}': {exc}", ErrorKind.INVALID) from exc
        if on_start:
            on_start(script, spec)

        async def go() -> ScriptResult:
            try:
                await session.open()
            except Exception as exc:  # noqa: BLE001 - the port could not be opened
                raise ServiceError(f"cannot use transport: {exc}", ErrorKind.TRANSPORT) from exc
            try:
                return await self.run_on(session, script, on_step=on_step, on_log=on_log)
            finally:
                await session.close()

        result = asyncio.run(go())
        if recorder and record_file:
            recorder.export_jsonl(record_file)
        if report_file:
            Path(report_file).write_text(json.dumps(result.to_dict(), indent=2, default=str), encoding="utf-8")
        return ScriptOutcome(script, spec, result)

    async def run_on(
        self,
        session: SerialSession,
        script: ScriptSpec,
        on_step: Optional[Callable[[StepResult], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> ScriptResult:
        """Run ``script`` on an already open session (the web API's shared link)."""
        return await ScriptRunner(script, session, on_step=on_step, on_log=on_log).run()


@dataclass
class DocsOutcome:
    """Files written by a documentation run, and protocol files that could not be documented."""

    written: List[Path] = field(default_factory=list)
    site: Optional[Path] = None
    failures: List[str] = field(default_factory=list)


def _doc_stem(name: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "_", name.lower()).strip("_") or "protocol"


class DocumentationService:
    """Service for generating protocol documentation."""

    def __init__(self, catalog: Optional[CatalogService] = None) -> None:
        self.catalog = catalog or CatalogService()

    def generate(
        self,
        protocol: Optional[str] = None,
        all_protocols: bool = False,
        fmt: str = "html",
        output_dir: str = "_site",
    ) -> DocsOutcome:
        """Document one protocol, or all of them (the HTML site, or one Markdown file per protocol)."""
        from omniuart.docs_generator import build_site_documentation, generate_html_docs, generate_markdown_docs

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        outcome = DocsOutcome()
        if all_protocols or not protocol:
            if fmt == "html":
                outcome.site = build_site_documentation(out)
                return outcome
            for pf in self.catalog.catalog.list_protocol_files():
                try:
                    spec = self.catalog.get_protocol(pf.name)
                except ServiceError as exc:
                    logger.warning("Skipping documentation for %s: %s", pf.name, exc)
                    outcome.failures.append(f"{pf.name}: {exc}")
                    continue
                target = out / f"{pf.stem}.md"
                target.write_text(generate_markdown_docs(spec), encoding="utf-8")
                outcome.written.append(target)
            return outcome

        spec = self.catalog.get_protocol(protocol)
        target = out / f"{_doc_stem(spec.metadata.name)}.{'html' if fmt == 'html' else 'md'}"
        target.write_text(generate_html_docs(spec) if fmt == "html" else generate_markdown_docs(spec), encoding="utf-8")
        outcome.written.append(target)
        return outcome


@dataclass
class FuzzOutcome:
    """A finished fuzzing campaign and the target it ran against."""

    report: FuzzReport
    target: str


class FuzzingService:
    """Service for protocol fuzzing and stress testing campaigns."""

    def __init__(self, catalog: Optional[CatalogService] = None) -> None:
        self.catalog = catalog or CatalogService()

    def run(
        self,
        protocol: str,
        vectors: int = 20,
        seed: Optional[int] = None,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        virtual: bool = False,
        read_only: bool = False,
        confirmed: bool = False,
    ) -> FuzzOutcome:
        """Fuzz a real port or the simulated device. Destructive commands go to hardware only when ``confirmed``."""
        try:
            spec = self.catalog.get_protocol(protocol)
        except ServiceError as exc:
            raise ServiceError(str(exc), ErrorKind.INVALID) from exc  # bad input for a campaign, not a failed one
        if read_only:
            spec.commands = [c for c in spec.commands if c.is_read_only]
            if not spec.commands:
                raise ServiceError(f"Protocol '{spec.metadata.name}' has no read-only commands to fuzz.", ErrorKind.INVALID)
        real_port = bool(port) and not virtual
        if real_port and not confirmed and any(c.safety is CommandSafety.DESTRUCTIVE for c in spec.commands):
            raise ServiceError("protocol contains destructive commands. Confirm with --yes or use --read-only.", ErrorKind.CONFIRMATION_REQUIRED)

        transport: AsyncTransport
        if real_port:
            assert port is not None
            baud = baudrate or spec.serial_config.baudrate
            transport, target = HardwareSerialTransport(port=port, baudrate=baud), f"{port} ({baud} bps)"
        else:
            transport, target = VirtualTransport(spec, latency_ms=1.0), "virtual simulator"
        try:
            report = asyncio.run(ProtocolFuzzer(spec, seed=seed).run_campaign(transport, max_vectors=vectors))
        except CodecError as exc:
            raise ServiceError(f"cannot fuzz '{spec.metadata.name}': {exc}", ErrorKind.INVALID) from exc
        except Exception as exc:  # noqa: BLE001 - any other failure is the link
            raise ServiceError(f"transport link error during fuzzing: {exc}", ErrorKind.TRANSPORT) from exc
        return FuzzOutcome(report, target)


class ReplayService:
    """Service for replaying recorded session logs."""

    def replay(
        self,
        session_file: str,
        port: Optional[str] = None,
        baudrate: Optional[int] = None,
        virtual: bool = False,
        speed: float = 1.0,
    ) -> ReplayResult:
        transport: AsyncTransport
        if port and not virtual:
            transport = HardwareSerialTransport(port=port, baudrate=baudrate or 115200)
        else:
            transport = VirtualTransport(latency_ms=1.0)

        async def go() -> ReplayResult:
            await transport.open()
            try:
                return await SessionReplayer(transport=transport, speed_multiplier=speed).replay_file(session_file)
            finally:
                await transport.close()

        try:
            return asyncio.run(go())
        except FileNotFoundError as exc:
            raise ServiceError(str(exc), ErrorKind.NOT_FOUND) from exc
        except ValueError as exc:
            raise ServiceError(str(exc), ErrorKind.INVALID) from exc


class GeneratorService:
    """Service for generating protocol code, Wireshark dissectors, AsyncAPI documents and schemas."""

    TARGETS = ("wireshark", "c", "python", "schema", "asyncapi")

    def __init__(self, catalog: Optional[CatalogService] = None) -> None:
        self.catalog = catalog or CatalogService()

    def generate(self, target: str, protocol: Optional[str] = None) -> str:
        from omniuart.core.asyncapi_exporter import export_asyncapi_json
        from omniuart.generators import (
            generate_c_header,
            generate_json_schema,
            generate_python_dataclasses,
            generate_wireshark_dissector,
        )

        if target == "schema":
            return generate_json_schema()
        if target not in self.TARGETS:
            raise ServiceError(f"Unknown generation target '{target}'.", ErrorKind.INVALID)
        if not protocol:
            raise ServiceError(f"protocol identifier is required for target '{target}'", ErrorKind.INVALID)
        spec = self.catalog.get_protocol(protocol, first=True)
        generators: Dict[str, Callable[[ProtocolSpec], str]] = {
            "wireshark": generate_wireshark_dissector,
            "c": generate_c_header,
            "python": generate_python_dataclasses,
            "asyncapi": export_asyncapi_json,
        }
        return generators[target](spec)
