"""FastAPI APIRouter Definition for OmniUART REST & WebSocket Streaming Endpoints."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import CodecError
from omniuart.core.models import CommandSpec, ProtocolSpec
from omniuart.core.recorder import SessionRecorder
from omniuart.core.runner import ScriptRunner, StepStatus
from omniuart.core.session import CommandBlockedError, ExchangeStatus
from omniuart.ui.connection import VIRTUAL_PORT, ConnectionManager, NotConnectedError
from omniuart.ui.models import CommandRequest, SerialConnectRequest
from omniuart.ui.views import get_index_html

logger = logging.getLogger(__name__)

router = APIRouter()
catalog = CatalogManager()
recorder = SessionRecorder()
active_connections: Set[WebSocket] = set()

# The single serial link shared by every request
connection = ConnectionManager()


async def broadcast_packet(packet_data: Dict[str, Any]) -> None:
    """Broadcast raw/decoded packet event to all connected WebSocket UI clients."""
    disconnected = set()
    for ws in list(active_connections):
        try:
            await ws.send_json(packet_data)
        except Exception:
            disconnected.add(ws)
    active_connections.difference_update(disconnected)


@router.websocket("/ws/serial")
async def websocket_serial_stream(websocket: WebSocket) -> None:
    """Bidirectional WebSocket streaming endpoint for 60 FPS traffic monitor & telemetry control."""
    await websocket.accept()
    active_connections.add(websocket)
    try:
        await websocket.send_json({
            "event": "connected",
            "message": "Connected to OmniUART WebSocket Serial Stream",
            "timestamp": time.time(),
        })
        while True:
            raw_text = await websocket.receive_text()
            try:
                import json
                msg = json.loads(raw_text)
                if msg.get("action") == "clear":
                    recorder.clear()
                    await websocket.send_json({"event": "cleared"})
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.discard(websocket)


@router.get("/api/protocols")
def get_protocols() -> Dict[str, Any]:
    """Return summary of all protocols discovered in definition directories."""
    return catalog.catalog_summary()


@router.get("/api/protocol/{identifier}")
def get_protocol_spec(identifier: str) -> Dict[str, Any]:
    """Return parsed protocol specification and tag breakdown."""
    spec = _load_protocol(identifier)

    tag_groups: Dict[str, List[str]] = {}
    for cmd in spec.commands:
        tags = cmd.tags if cmd.tags else ["general"]
        for tag in tags:
            tag_groups.setdefault(tag, []).append(cmd.name)

    return {
        "spec": spec.model_dump(),
        "tags": list(tag_groups.keys()),
        "tag_groups": tag_groups,
    }


@router.get("/api/serial/ports")
def list_serial_ports() -> Dict[str, Any]:
    """Enumerate the serial ports present on this machine (never invented), plus the simulated device."""
    from omniuart.core.transport import list_available_ports

    try:
        ports = [p["device"] for p in list_available_ports()]
    except Exception:  # noqa: BLE001 - enumeration can fail on locked-down systems
        ports = []
    return {
        "ports": ports,
        "virtual_port": VIRTUAL_PORT,
        "current": connection.state(),
    }


@router.post("/api/serial/connect")
async def connect_serial(req: SerialConnectRequest) -> Dict[str, Any]:
    """Open the requested serial port (or the labelled simulated device), replacing any open link."""
    if req.port == VIRTUAL_PORT:
        try:
            known = bool(req.protocol) and catalog.get_protocol(req.protocol) is not None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not known:
            raise HTTPException(status_code=422, detail="The virtual device needs a valid 'protocol' to simulate.")
    try:
        await connection.connect(req.port, req.baudrate, req.rts, req.dtr, req.read_only)
    except Exception as exc:  # noqa: BLE001 - port missing, busy or not permitted
        raise HTTPException(status_code=400, detail=f"Cannot open port '{req.port}': {exc}") from exc
    return {"status": "success", "connection": connection.state()}


@router.post("/api/serial/disconnect")
async def disconnect_serial() -> Dict[str, Any]:
    """Close the open link. Disconnecting when nothing is open is not an error."""
    await connection.disconnect()
    return {"status": "success", "connection": connection.state()}


@router.get("/api/serial/status")
def serial_status() -> Dict[str, Any]:
    return {"connection": connection.state()}


def _load_protocol(identifier: str) -> ProtocolSpec:
    """Return the named protocol: 404 when there is none, 422 when its file fails to load (#339)."""
    try:
        spec = catalog.get_protocol(identifier)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not spec:
        raise HTTPException(status_code=404, detail=f"Protocol '{identifier}' not found")
    return spec


def _resolve(identifier: str, command: str) -> Tuple[ProtocolSpec, CommandSpec]:
    spec = _load_protocol(identifier)
    cmd = spec.get_command(command) or spec.get_command_by_id(command)
    if not cmd:
        raise HTTPException(status_code=404, detail=f"Command '{command}' not found")
    return spec, cmd


async def _publish(events: List[Any]) -> None:
    """Add a request's recorded frames to the shared log and stream them to WebSocket clients."""
    for event in events:
        if event is not None:
            recorder.add_event(event)
            await broadcast_packet(event.model_dump())


def _not_connected(exc: NotConnectedError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


_FAILURE_CODES = {
    ExchangeStatus.TIMEOUT: 504,
    ExchangeStatus.INVALID_RESPONSE: 502,
    ExchangeStatus.TRANSPORT_ERROR: 502,
}


@router.post("/api/send/{identifier}")
async def send_command(identifier: str, req: CommandRequest) -> Any:
    """Encode the command, transmit it on the open link and return the decoded device response.

    Failures are real HTTP errors: 404 unknown protocol/command, 409 not connected, 422 invalid
    parameters, 504 no response, 502 invalid response or link failure, 403 command refused by a
    read-only connection, 428 a mutating or destructive command sent without ``confirm: true``.
    """
    spec, cmd = _resolve(identifier, req.command)
    if cmd.needs_confirmation and not req.confirm and not (connection.read_only):
        raise HTTPException(
            status_code=428,
            detail=f"'{cmd.name}' is {cmd.safety.value}: resend with \"confirm\": true to send it.",
        )
    temp = SessionRecorder()
    try:
        async with connection.use(spec, temp) as session:
            exchange = await session.send(cmd, req.params)
    except NotConnectedError as exc:
        raise _not_connected(exc) from exc
    except CommandBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CodecError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await _publish(temp.events)

    body: Dict[str, Any] = {
        "status": "success" if exchange.ok else "failed",
        "protocol": spec.metadata.name,
        "command": cmd.name,
        "sent_params": req.params,
        "request_hex": exchange.request.hex(" ").upper(),
        "response_hex": exchange.response_bytes.hex(" ").upper(),
        "decoded_response": exchange.fields,
        "latency_ms": round(exchange.latency_ms, 2),
        "simulated": connection.virtual,
    }
    if not exchange.ok:
        body["error"] = exchange.error
        return JSONResponse(status_code=_FAILURE_CODES[exchange.status], content=body)
    return body


@router.get("/api/scripts")
def list_scripts() -> Dict[str, Any]:
    """Return available automated test scripts."""
    script_files = catalog.list_script_files()
    return {
        "scripts": [
            {
                "name": f.stem,
                "filename": f.name,
                "path": str(f),
            }
            for f in script_files
        ]
    }


@router.post("/api/script/run/{script_name}")
async def run_script(script_name: str) -> Any:
    """Execute a script with the shared runner and return the real per-step results.

    404 unknown script, 409 not connected, 422 invalid script, 502 link failure. A script whose
    assertions fail returns 200 with ``"status": "FAILED"``.
    """
    script = catalog.get_script(script_name)
    if not script:
        raise HTTPException(status_code=404, detail=f"Script '{script_name}' not found")
    spec = None
    for ref in (script.meta.protocol, Path(script.meta.protocol).name, Path(script.meta.protocol).stem):
        try:
            spec = catalog.get_protocol(ref) if ref else None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if spec:
            break
    if spec is None:
        raise HTTPException(status_code=422, detail=f"Protocol '{script.meta.protocol}' for this script was not found")

    temp = SessionRecorder()
    try:
        async with connection.use(spec, temp) as session:
            result = await ScriptRunner(script, session).run()
    except NotConnectedError as exc:
        raise _not_connected(exc) from exc
    await _publish(temp.events)

    report = result.to_dict()
    counts = {s: sum(1 for step in result.steps if step.status is s) for s in StepStatus}
    body = {
        **report,
        "script": script_name,
        "status": "PASSED" if result.passed else "FAILED",
        "total_steps": len(result.steps),
        "passed_steps": counts[StepStatus.PASSED],
        "failed_steps": counts[StepStatus.FAILED] + counts[StepStatus.ERROR],
        "simulated": connection.virtual,
    }
    if result.exit_code == 3:
        return JSONResponse(status_code=502, content=body)
    if result.exit_code == 2:
        return JSONResponse(status_code=422, content=body)
    return body


@router.get("/api/dashboard/auto-run/{identifier}")
async def dashboard_auto_run(identifier: str) -> Dict[str, Any]:
    """Really run every ``dashboard``-tagged, ``read_only`` command that needs no input and report each outcome.

    A dashboard command that is not marked ``safety: read_only`` is reported as skipped, never sent.
    """
    spec = _load_protocol(identifier)

    dashboard_cmds = [cmd for cmd in spec.commands if "dashboard" in cmd.tags]
    temp = SessionRecorder()
    results: Dict[str, Any] = {}
    try:
        async with connection.use(spec, temp) as session:
            for cmd in dashboard_cmds:
                if not cmd.is_read_only:
                    results[cmd.name] = {"command_id": cmd.id, "status": "SKIPPED", "error": f"not marked safety: read_only (it is {cmd.safety.value})"}
                    continue
                missing = [p.name for p in cmd.parameters if p.default is None]
                if missing:
                    results[cmd.name] = {"command_id": cmd.id, "status": "SKIPPED", "error": f"needs a value for: {', '.join(missing)}"}
                    continue
                try:
                    exchange = await session.send(cmd, {})
                except CodecError as exc:
                    results[cmd.name] = {"command_id": cmd.id, "status": "FAILED", "error": str(exc)}
                    continue
                results[cmd.name] = {
                    "command_id": cmd.id,
                    "status": "SUCCESS" if exchange.ok else "FAILED",
                    "response": exchange.fields if exchange.ok else None,
                    "error": exchange.error,
                }
    except NotConnectedError as exc:
        raise _not_connected(exc) from exc
    await _publish(temp.events)

    return {
        "protocol": spec.metadata.name,
        "dashboard_commands_executed": sum(1 for r in results.values() if r["status"] != "SKIPPED"),
        "data": results,
        "simulated": connection.virtual,
    }


@router.get("/api/ports")
def get_available_serial_ports() -> Dict[str, Any]:
    """Scan and return list of detected hardware serial ports."""
    from omniuart.core.transport import list_available_ports
    return {"ports": list_available_ports()}


@router.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the single-page Tag-Based Dynamic Web UI application with Workspace Navigation."""
    return get_index_html()


@router.get("/designer", response_class=HTMLResponse)
@router.get("/designer/{identifier}", response_class=HTMLResponse)
def get_designer_view(identifier: Optional[str] = None) -> str:
    """Serve the visual Device UI Designer editor interface (#241)."""
    from omniuart.core.device_ui import DeviceUIStore
    from omniuart.designer import generate_designer_html

    store = DeviceUIStore()
    if identifier:
        spec = _load_protocol(identifier)
    else:
        proto_files = catalog.list_protocol_files()
        if not proto_files:
            raise HTTPException(status_code=404, detail="No protocols available in catalog for designer")
        spec = _load_protocol(proto_files[0].name)

    ui_spec = store.find_for_protocol(spec.metadata.name)
    return generate_designer_html(spec, ui_spec)


@router.get("/api/designer/spec/{identifier}")
def get_designer_protocol_spec(identifier: str) -> Dict[str, Any]:
    """Return protocol spec and inferred or stored DeviceUISpec for designer (#241, #242)."""
    from omniuart.core.device_ui import DeviceUIStore, infer_device_ui_from_spec

    spec = _load_protocol(identifier)
    store = DeviceUIStore()
    ui_spec = store.find_for_protocol(spec.metadata.name) or infer_device_ui_from_spec(spec)
    return {
        "protocol": spec.model_dump(),
        "ui_spec": ui_spec.model_dump(),
    }


@router.post("/api/designer/validate")
def validate_designer_spec(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a draft DeviceUISpec against a protocol for compatibility (#241, #242)."""
    from omniuart.core.device_ui import check_protocol_compatibility

    proto_name = payload.get("protocol")
    if not proto_name:
        raise HTTPException(status_code=400, detail="Missing protocol identifier in payload")
    spec = _load_protocol(proto_name)
    report = check_protocol_compatibility(_designer_ui_spec(payload), spec)
    return report.model_dump()


@router.post("/api/designer/save")
def save_designer_spec(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a draft DeviceUISpec to the UI store repository (#241, #242)."""
    from omniuart.core.device_ui import DeviceUIStore, import_device_ui

    ui_spec = _designer_ui_spec(payload)
    fmt = payload.get("format", "yaml")
    try:
        path = DeviceUIStore().save(ui_spec, format=fmt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = import_device_ui(path.read_text(encoding="utf-8"))
    return {"ok": True, "path": str(path), "filename": path.name, "revision": saved.revision}


@router.post("/api/designer/export", response_class=PlainTextResponse)
def export_designer_spec(payload: Dict[str, Any]) -> str:
    """Return a draft DeviceUISpec as YAML or JSON text (#241, #242)."""
    from omniuart.core.device_ui import export_device_ui

    ui_spec = _designer_ui_spec(payload)
    try:
        return export_device_ui(ui_spec, format=payload.get("format", "yaml"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/designer/preview", response_class=HTMLResponse)
def preview_designer_spec(payload: Dict[str, Any]) -> str:
    """Render the device dashboard for a draft DeviceUISpec, so the designer can preview it (#241)."""
    from omniuart.dashboard_generator import generate_device_dashboard_html

    proto_name = payload.get("protocol")
    if not proto_name:
        raise HTTPException(status_code=400, detail="Missing protocol identifier in payload")
    spec = _load_protocol(proto_name)
    return generate_device_dashboard_html(spec, _designer_ui_spec(payload), connection_status="PREVIEW", is_connected=False)


def _designer_ui_spec(payload: Dict[str, Any]) -> Any:
    from omniuart.core.device_ui import migrate_ui_spec

    ui_dict = payload.get("ui_spec")
    if not isinstance(ui_dict, dict) or not ui_dict:
        raise HTTPException(status_code=400, detail="Missing ui_spec in payload")
    try:
        return migrate_ui_spec(ui_dict)
    except ValueError as exc:  # pydantic.ValidationError is a ValueError
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/designer/definitions")
def list_designer_definitions() -> Dict[str, Any]:
    """List all stored Device UI definitions (#242)."""
    from omniuart.core.device_ui import DeviceUIStore

    store = DeviceUIStore()
    return {"definitions": store.list_definitions()}
