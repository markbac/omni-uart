"""Dashboard HTML Generator for OmniUART Device UI / Device Explorer (#230, #235, #236, #246, #316, #318).

Generates the device control console from a ProtocolSpec and a DeviceUISpec. Every widget is bound to
the protocol: command buttons and parameter controls send real commands through the web API (with the
command's safety rules), display widgets show values the device actually sent, with their quality,
and transfer widgets upload files through the device's declared transfer commands. The Engineer and
Developer views show the recorded traffic. Every interpolated value is HTML-escaped.

The page talks to these endpoints (see ``ui/routes.py``): ``GET /api/device/{id}/state``,
``POST /api/device/{id}/refresh``, ``POST /api/send/{id}`` and ``/api/device/{id}/transfer``.
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List, Optional

from omniuart.core.device_ui import DeviceUISpec, PanelSpec, WidgetSpec, infer_device_ui_from_spec
from omniuart.core.models import CommandSafety, CommandSpec, FieldSpec, ProtocolSpec

_INPUT_TYPES = {"slider", "switch", "checkbox", "bool", "dropdown", "enum", "number_input", "text_input", "input", "paired_register", "register"}
_TRANSFER_TYPES = {"file_transfer", "firmware_update"}
_CSP = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:"


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _json_for_script(data: Any) -> str:
    """JSON safe to place inside a <script> element (whose content is never entity-decoded)."""
    return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _owning_command(spec: ProtocolSpec, ref: str) -> Optional[tuple[CommandSpec, FieldSpec]]:
    """The command and parameter a widget's ``field_ref`` names (``cmd.param`` or a bare parameter name)."""
    if "." in ref:
        cmd_name, param = ref.split(".", 1)
        cmd = spec.get_command(cmd_name)
        found = next((p for p in cmd.parameters if p.name == param), None) if cmd else None
        return (cmd, found) if cmd and found else None
    for cmd in spec.commands:
        for p in cmd.parameters:
            if p.name == ref:
                return cmd, p
    return None


def resolve_widget(spec: ProtocolSpec, widget: WidgetSpec) -> Dict[str, Any]:
    """Decide what a widget does: ``command``, ``param`` (input for a command parameter), ``transfer`` or ``display``."""
    ref = widget.field_ref or ""
    wtype = widget.widget_type.lower()
    if wtype in _TRANSFER_TYPES:
        return {"role": "transfer", "command": ref}
    cmd = spec.get_command(ref) if ref else None
    if cmd is not None and (wtype in ("button", "action") or not cmd.parameters):
        return {"role": "command", "command": cmd.name}
    owner = _owning_command(spec, ref) if ref else None
    if owner is not None and (wtype in _INPUT_TYPES or wtype in ("button", "action")):
        return {"role": "param", "command": owner[0].name, "param": owner[1]}
    field = ref.split(".", 1)[1] if "." in ref else ref
    return {"role": "display", "field": field}


def _command_config(spec: ProtocolSpec, ui: DeviceUISpec) -> Dict[str, Any]:
    rules = {r.command: r for r in ui.safety_rules}
    out: Dict[str, Any] = {}
    for cmd in spec.commands:
        rule = rules.get(cmd.name)
        out[cmd.name] = {
            "safety": cmd.safety.value,
            # The protocol's safety is the floor: a rule can add a confirmation, never remove one.
            "confirm": cmd.needs_confirmation or bool(rule and rule.require_confirmation),
            "warning": (rule.warning_message if rule else None) or None,
            "danger": bool(rule and rule.danger_zone) or cmd.safety is CommandSafety.DESTRUCTIVE,
        }
    return out


def _transfer_problem(spec: ProtocolSpec, ui: DeviceUISpec) -> Optional[str]:
    """Why transfers cannot run for this device, or None when they can."""
    from omniuart.core.transfer_session import TransferDefinitionError, transfer_commands

    if ui.transfer_protocol is None:
        return "This device's UI definition declares no transfer_protocol, so files cannot be sent."
    try:
        transfer_commands(spec, ui.transfer_protocol)
    except TransferDefinitionError as exc:
        return f"Transfer definition does not match the protocol: {exc}"
    return None


def _param_control(widget: WidgetSpec, param: FieldSpec, command: str, css: str) -> str:
    """The input element for a command parameter."""
    wtype = widget.widget_type.lower()
    attrs = f'data-command="{_esc(command)}" data-param="{_esc(param.name)}" data-type="{_esc(param.type.value)}"'
    lo = widget.min if widget.min is not None else param.min
    hi = widget.max if widget.max is not None else param.max
    default = param.default
    options = widget.options or param.options
    if wtype in ("dropdown", "enum") or options:
        opts = "".join(
            f'<option value="{_esc(k)}"{" selected" if default is not None and str(k) == str(default) else ""}>{_esc(v)}</option>'
            for k, v in (options or {}).items()
        )
        return f'<select class="{css}-select" {attrs}>{opts}</select>'
    if wtype in ("switch", "checkbox", "bool"):
        checked = " checked" if default else ""
        return f'<input type="checkbox" class="toggle" {attrs}{checked}>'
    if wtype == "slider" and lo is not None and hi is not None:
        step = widget.step or (0.1 if param.type.value.startswith("float") else 1)
        value = default if default is not None else lo
        return (
            f'<input type="range" class="widget-slider" min="{_esc(lo)}" max="{_esc(hi)}" step="{_esc(step)}" value="{_esc(value)}" {attrs}>'
            f'<output class="slider-value">{_esc(value)}</output>'
        )
    if wtype in ("number_input", "slider") or param.type.value.startswith(("uint", "int", "float")):
        bounds = "".join(f' {k}="{_esc(v)}"' for k, v in (("min", lo), ("max", hi), ("step", widget.step)) if v is not None)
        return f'<input type="number" class="{css}-input"{bounds} value="{_esc(default)}" {attrs}>'
    return f'<input type="text" class="{css}-input" value="{_esc(default)}" {attrs}>'


def _display(widget: WidgetSpec, field: str) -> str:
    wtype = widget.widget_type.lower()
    ref = f'data-field="{_esc(field)}"'
    if wtype == "gauge":
        lo = widget.min if widget.min is not None else 0
        hi = widget.max if widget.max is not None else 100
        return (
            f'<div class="gauge-container"><div class="gauge-bar-bg"><div class="gauge-bar-fill" {ref} data-min="{_esc(lo)}" data-max="{_esc(hi)}"></div></div>'
            f'<span class="value" {ref}>--</span></div>'
        )
    if wtype == "line_plot":
        return f'<svg class="sparkline" viewBox="0 0 120 30" {ref}><polyline points="" /></svg><span class="value" {ref}>--</span>'
    if wtype == "badge":
        return f'<span class="value pill" {ref}>--</span>'
    if wtype in ("lcd_matrix", "lcd_display"):
        return f'<span class="value lcd" {ref}>--</span>'
    return f'<span class="value" {ref}>--</span>'


def _transfer_card(widget: WidgetSpec, problem: Optional[str], css_prefix: str = "") -> str:
    ref = _esc(widget.field_ref)
    label = _esc(widget.label)
    accept = _esc(",".join(widget.supported_file_types or []))
    max_size = int(widget.max_size_bytes or 16 * 1024 * 1024)
    transfer_type = _esc((widget.transfer_type or "binary").upper())
    prompt = _esc(widget.confirm_prompt)
    warning = _esc(widget.safety_warning)
    badge = "transfer-badge transfer-danger" if widget.destructive else "transfer-badge"
    alert = ""
    if widget.destructive or widget.safety_warning:
        alert = f'<div class="safety-alert">⚠️ {warning or prompt or "Warning: Destructive device operation."}</div>'
    disabled = " disabled" if problem else ""
    note = f'<div class="transfer-unavailable">{_esc(problem)}</div>' if problem else ""
    return f"""      <div class="transfer-card {css_prefix}" data-transfer-ref="{ref}" data-destructive="{str(widget.destructive).lower()}" data-max-size="{max_size}" data-accept="{accept}" data-prompt="{prompt}">
        <div class="transfer-header"><strong>{label}</strong><span class="{badge}">{transfer_type}</span></div>
        <div class="transfer-meta-text"><span>Supported: {accept or "any"} | Max: {round(max_size / (1024 * 1024), 1)} MB</span>
          <span class="transfer-state" style="font-weight:600;">IDLE</span></div>
        {alert}{note}
        <input type="file" class="file-input" accept="{accept}"{disabled} />
        <div class="progress-bar-bg"><div class="progress-bar-fill"></div></div>
        <div class="transfer-meta-text"><span class="transfer-progress">0% | 0 kB/s</span><span class="transfer-eta">ETA: --</span></div>
        <div class="transfer-message"></div>
        <div class="transfer-actions">
          <button class="btn btn-transfer" data-action="start-transfer"{disabled}>Start Transfer</button>
          <button class="btn btn-cancel" data-action="cancel-transfer" disabled>Cancel</button>
          <button class="btn btn-retry" data-action="retry-transfer" disabled>Retry</button>
        </div>
      </div>
"""


def _safety_badge(cmd_cfg: Dict[str, Any]) -> str:
    if cmd_cfg["safety"] == "read_only":
        return ""
    return f' <span class="safety safety-{_esc(cmd_cfg["safety"])}">{_esc(cmd_cfg["safety"])}</span>'


def _widget_html(spec: ProtocolSpec, widget: WidgetSpec, commands: Dict[str, Any], transfer_problem: Optional[str]) -> str:
    info = resolve_widget(spec, widget)
    label = _esc(widget.label)
    unit = f" ({_esc(widget.unit)})" if widget.unit else ""
    if info["role"] == "transfer":
        return _transfer_card(widget, transfer_problem)
    if info["role"] == "command":
        cmd = info["command"]
        return (
            f'      <div class="widget-row"><span>{label}{_safety_badge(commands[cmd])}</span>'
            f'<button class="btn" data-role="command" data-command="{_esc(cmd)}">Send</button></div>\n'
        )
    if info["role"] == "param":
        cmd = info["command"]
        control = _param_control(widget, info["param"], cmd, "widget")
        return (
            f'      <div class="widget-row"><span>{label}{unit}{_safety_badge(commands[cmd])}</span>'
            f'<span class="control">{control}<button class="btn" data-role="command" data-command="{_esc(cmd)}">Set</button></span></div>\n'
        )
    return f'      <div class="widget-row"><span>{label}{unit}</span>{_display(widget, info["field"])}</div>\n'


def generate_device_dashboard_html(
    spec: ProtocolSpec,
    ui_spec: Optional[DeviceUISpec] = None,
    connection_status: Optional[str] = None,
    is_connected: Optional[bool] = None,
    api_identifier: Optional[str] = None,
) -> str:
    """Generate the Device Control Console HTML for ``spec``.

    ``ui_spec`` defaults to the UI inferred from the protocol. The status badge starts from
    ``is_connected`` (or ``connection_status``) and is then kept current from the web API, using
    ``api_identifier`` (default: the protocol name) to address this protocol.
    """
    ui = ui_spec or infer_device_ui_from_spec(spec)
    if is_connected is not None:
        status_label = "CONNECTED" if is_connected else "DISCONNECTED"
    else:
        status_label = (connection_status or "CHECKING").upper()
    baudrate = spec.serial_config.baudrate
    commands = _command_config(spec, ui)
    config = {
        "api": api_identifier or spec.metadata.name,
        "baudrate": baudrate,
        "commands": commands,
    }
    identity = {
        "name": _esc(ui.identity.name or spec.metadata.name),
        "model": _esc(ui.identity.model or "Universal UART Device"),
        "vendor": _esc(ui.identity.vendor or spec.metadata.author or "OmniUART"),
        "version": _esc(ui.identity.version or spec.metadata.version),
    }
    if str(ui.theme).lower() in ("win32", "classic", "desktop", "industrial"):
        return _generate_win32_dashboard_html(spec, ui, identity, status_label, commands, config)

    transfer_problem = _transfer_problem(spec, ui)
    connected_class = "status-connected" if status_label == "CONNECTED" else "status-disconnected"
    body: List[str] = []
    for panel in ui.panels:
        body.append(f'    <h2 class="panel-title">{_esc(panel.title)}</h2>\n')
        for group in panel.groups:
            body.append(f'    <div class="group-card">\n      <h3>{_esc(group.title)}</h3>\n')
            body.extend(_widget_html(spec, w, commands, transfer_problem) for w in group.widgets)
            body.append("    </div>\n")

    integrity = spec.framing.integrity.algorithm if spec.framing.integrity else "none"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="{_CSP}">
  <title>⚡ {identity["name"]} - Device Control Console</title>
  <style>
    :root {{ --bg: #0f172a; --panel: #1e293b; --accent: #38bdf8; --text: #f8fafc; --muted: #94a3b8;
      --border: #334155; --success: #22c55e; --warning: #f59e0b; --danger: #ef4444; }}
    body {{ margin: 0; padding: 20px; background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }}
    .header {{ display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; padding: 16px 24px;
      background: var(--panel); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 20px; }}
    .device-title {{ font-size: 1.4rem; font-weight: bold; color: var(--accent); }}
    .muted {{ color: var(--muted); font-size: 0.9rem; }}
    .header-actions {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
    .status-badge {{ padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; }}
    .status-connected {{ background: #14532d; color: var(--success); }}
    .status-disconnected {{ background: #7f1d1d; color: #fca5a5; }}
    .dashboard-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }}
    .panel-title {{ grid-column: 1 / -1; color: var(--accent); margin: 16px 0 0; }}
    .group-card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }}
    .group-card h3 {{ margin-top: 0; color: var(--accent); }}
    .widget-row {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border); }}
    .widget-row:last-child {{ border-bottom: none; }}
    .control {{ display: flex; gap: 8px; align-items: center; }}
    .btn {{ background: var(--accent); color: #000; font-weight: 600; padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer; }}
    .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}
    .btn-secondary {{ background: #475569; color: #fff; }}
    .value {{ font-variant-numeric: tabular-nums; font-weight: 600; }}
    .q-stale {{ color: var(--warning); }} .q-offline, .q-none {{ color: var(--muted); }}
    .pill {{ background: #0369a1; padding: 2px 10px; border-radius: 10px; }}
    .lcd {{ font-family: monospace; background: #15803d; color: #052e16; padding: 4px 8px; border-radius: 3px; }}
    .safety {{ font-size: 0.7rem; padding: 1px 6px; border-radius: 4px; background: #78350f; color: #fde68a; margin-left: 6px; }}
    .safety-destructive {{ background: #7f1d1d; color: #fecaca; }}
    .gauge-container {{ display: flex; align-items: center; gap: 12px; }}
    .gauge-bar-bg {{ background: #0f172a; width: 120px; height: 10px; border-radius: 5px; overflow: hidden; }}
    .gauge-bar-fill {{ background: var(--accent); height: 100%; width: 0%; }}
    .sparkline {{ width: 120px; height: 30px; }} .sparkline polyline {{ fill: none; stroke: var(--accent); stroke-width: 1.5; }}
    .widget-slider {{ width: 140px; }}
    .widget-select, .widget-input {{ background: #0f172a; border: 1px solid var(--border); color: #fff; padding: 4px 8px; border-radius: 4px; max-width: 140px; }}
    .transfer-card {{ background: #111827; border: 1px solid #374151; border-radius: 8px; padding: 12px; margin: 10px 0; }}
    .transfer-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
    .transfer-badge {{ background: #0369a1; color: #fff; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; }}
    .transfer-danger {{ background: #991b1b; color: #fecaca; }}
    .transfer-unavailable {{ color: var(--warning); font-size: 0.8rem; margin: 6px 0; }}
    .transfer-message {{ font-size: 0.8rem; min-height: 1em; }}
    .file-input {{ display: block; width: 100%; margin: 8px 0; font-size: 0.85rem; color: var(--muted); }}
    .progress-bar-bg {{ background: #1e293b; border-radius: 4px; height: 10px; width: 100%; overflow: hidden; margin: 8px 0; }}
    .progress-bar-fill {{ background: var(--accent); height: 100%; width: 0%; transition: width 0.3s; }}
    .transfer-meta-text {{ font-size: 0.8rem; color: var(--muted); display: flex; justify-content: space-between; margin-bottom: 4px; }}
    .safety-alert {{ background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); border-radius: 6px; padding: 8px; margin: 8px 0; font-size: 0.8rem; color: #fca5a5; }}
    .transfer-actions {{ display: flex; gap: 8px; margin-top: 10px; }}
    .btn-cancel {{ background: #475569; color: #fff; }} .btn-retry {{ background: #d97706; color: #fff; }}
    .mode-tabs {{ display: flex; gap: 10px; margin-bottom: 20px; }}
    .mode-tab {{ background: var(--panel); border: 1px solid var(--border); color: var(--muted); padding: 8px 18px; border-radius: 6px; cursor: pointer; font-weight: 600; }}
    .mode-tab.active {{ background: #0284c7; color: #fff; border-color: var(--accent); }}
    .mode-view {{ display: none; }} .mode-view.active {{ display: block; }}
    table.traffic {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    table.traffic th, table.traffic td {{ text-align: left; padding: 6px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    table.traffic td.hex {{ font-family: monospace; word-break: break-all; }}
    .ok {{ color: var(--success); }} .bad {{ color: var(--danger); }}
    pre.raw {{ background: #0f172a; padding: 12px; border-radius: 6px; color: #34d399; font-size: 0.8rem; overflow-x: auto; max-height: 420px; }}
    #toast {{ position: fixed; bottom: 20px; right: 20px; background: var(--panel); border: 1px solid var(--border); padding: 10px 16px; border-radius: 6px; display: none; max-width: 420px; }}
    #toast.error {{ border-color: var(--danger); }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="device-title">⚡ {identity["name"]} ({identity["model"]})</div>
      <div class="muted">Vendor: {identity["vendor"]} | Firmware: {identity["version"]}</div>
    </div>
    <div class="header-actions">
      <button class="btn btn-secondary" data-action="refresh" title="Send every read-only command that needs no input">Read device</button>
      <label class="muted"><input type="checkbox" data-action="auto-refresh"> Auto refresh</label>
      <span class="status-badge {connected_class}" id="connectionStatus">{_esc(status_label)} ({baudrate} bps)</span>
    </div>
  </div>

  <div class="mode-tabs">
    <button class="mode-tab active" data-mode="operator">Operator Mode</button>
    <button class="mode-tab" data-mode="engineer">Engineer Mode</button>
    <button class="mode-tab" data-mode="developer">Developer Mode</button>
  </div>

  <div id="operatorView" class="mode-view active">
    <div class="dashboard-grid" id="panelsContainer">
{"".join(body)}    </div>
  </div>

  <div id="engineerView" class="mode-view">
    <div class="group-card">
      <h3>🔧 Protocol traffic</h3>
      <p class="muted">Baud rate: {baudrate} bps | Framing: {_esc(spec.framing.type.value.upper())} | Integrity: {_esc(integrity)}. Newest first; select a row for its decoded fields.</p>
      <table class="traffic"><thead><tr><th>Command</th><th>Status</th><th>Latency</th><th>CRC</th><th>Request</th><th>Response</th></tr></thead>
        <tbody id="engineerRows"><tr><td colspan="6" class="muted">No exchanges yet.</td></tr></tbody></table>
      <pre class="raw" id="engineerDetail" hidden></pre>
    </div>
  </div>

  <div id="developerView" class="mode-view">
    <div class="group-card">
      <h3>💻 Raw frames and session</h3>
      <pre class="raw" id="rawLog">No frames yet.</pre>
      <h3>Connection</h3><pre class="raw" id="connectionJson">--</pre>
      <h3>Device state</h3><pre class="raw" id="stateJson">--</pre>
    </div>
  </div>

  <div id="toast"></div>
  <script type="application/json" id="dashboard-config">{_json_for_script(config)}</script>
  <script>{_RUNTIME_SCRIPT}</script>
</body>
</html>
"""


def _generate_win32_dashboard_html(
    spec: ProtocolSpec,
    ui: DeviceUISpec,
    identity: Dict[str, str],
    status_label: str,
    commands: Dict[str, Any],
    config: Dict[str, Any],
) -> str:
    """Classic Win32 / industrial utility layout over the same live runtime as the modern theme."""
    transfer_problem = _transfer_problem(spec, ui)
    panels = ui.panels or [PanelSpec(name="info", title="Info", groups=[])]
    tab_buttons: List[str] = []
    tab_panes: List[str] = []
    for idx, panel in enumerate(panels):
        active = " active" if idx == 0 else ""
        tab_buttons.append(f'<button type="button" class="win32-tab-button{active}" data-tab="{idx}">{_esc(panel.title)}</button>')
        fieldsets: List[str] = []
        for group in panel.groups:
            rows: List[str] = []
            for w in group.widgets:
                info = resolve_widget(spec, w)
                label = f"{_esc(w.label)}{f' ({_esc(w.unit)})' if w.unit else ''}"
                wtype = w.widget_type.lower()
                if info["role"] == "transfer":
                    rows.append(_transfer_card(w, transfer_problem, "win32-transfer-box"))
                elif wtype in ("lcd_matrix", "lcd_display"):
                    cells = "".join('<div class="win32-lcd-cell"> </div>' for _ in range(32))
                    rows.append(
                        f'<div class="win32-lcd-box"><div style="font-weight:bold;">{label}</div>'
                        f'<div class="win32-lcd-screen"><div class="win32-lcd-grid" data-lcd-field="{_esc(info.get("field", w.field_ref))}">{cells}</div></div>'
                        f'<button type="button" class="win32-btn win32-btn-get" data-action="refresh">Get</button></div>'
                    )
                elif info["role"] == "command":
                    rows.append(
                        f'<div class="win32-row"><button type="button" class="win32-btn" data-role="command" data-command="{_esc(info["command"])}">{_esc(w.label)}</button></div>'
                    )
                elif info["role"] == "param":
                    control = _param_control(w, info["param"], info["command"], "win32")
                    rows.append(
                        f'<div class="win32-row"><span class="win32-label">{label}</span>{control}'
                        f'<button type="button" class="win32-btn win32-btn-get" data-action="refresh">Get</button>'
                        f'<button type="button" class="win32-btn win32-btn-set" data-role="command" data-command="{_esc(info["command"])}">Set</button></div>'
                    )
                else:
                    rows.append(
                        f'<div class="win32-row"><span class="win32-label">{label}</span>'
                        f'<span class="win32-input value" data-field="{_esc(info["field"])}">--</span>'
                        f'<button type="button" class="win32-btn win32-btn-get" data-action="refresh">Get</button></div>'
                    )
            fieldsets.append(f'<fieldset class="win32-fieldset"><legend>{_esc(group.title)}</legend>{"".join(rows)}</fieldset>')
        tab_panes.append(f'<div class="win32-tab-pane{active}" data-pane="{idx}">{"".join(fieldsets)}</div>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="{_CSP}">
  <title>{identity["name"]} - V{identity["version"]}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #f0f0f0; color: #000; font-family: 'Segoe UI', Tahoma, Arial, sans-serif; font-size: 11px; }}
    .win32-window {{ min-height: 100vh; display: flex; flex-direction: column; }}
    .win32-topbar {{ display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; border-bottom: 1px solid #d0d0d0; }}
    .win32-btn {{ background: #e1e1e1; border: 1px solid #adadad; padding: 2px 10px; font-size: 11px; font-family: inherit; cursor: pointer; border-radius: 2px; min-width: 50px; }}
    .win32-btn:hover {{ background: #e5f1fb; border-color: #0078d7; }}
    .win32-btn:disabled {{ color: #888; cursor: not-allowed; }}
    .win32-input, .win32-select {{ display: inline-block; min-width: 90px; background: #fff; border: 1px solid #7a7a7a; padding: 2px 4px; font-size: 11px; font-family: inherit; }}
    .win32-tab-bar {{ display: flex; flex-wrap: wrap; background: #e5e5e5; border-bottom: 1px solid #adadad; padding: 4px 6px 0; gap: 2px; }}
    .win32-tab-button {{ background: #e1e1e1; border: 1px solid #adadad; border-bottom: none; padding: 4px 10px; font-size: 11px; cursor: pointer; }}
    .win32-tab-button.active {{ background: #f0f0f0; font-weight: bold; margin-bottom: -1px; }}
    .win32-tab-pane {{ display: none; padding: 12px; }}
    .win32-tab-pane.active {{ display: flex; flex-wrap: wrap; gap: 12px; align-content: flex-start; }}
    .win32-fieldset {{ border: 1px solid #d0d0d0; background: #fafafa; padding: 8px 12px; min-width: 240px; }}
    .win32-fieldset legend {{ font-weight: bold; color: #333; }}
    .win32-row {{ display: flex; align-items: center; gap: 6px; margin-bottom: 5px; }}
    .win32-label {{ min-width: 120px; }}
    .q-stale {{ color: #a16207; }} .q-offline, .q-none {{ color: #888; }}
    .win32-lcd-box {{ display: flex; flex-direction: column; align-items: center; gap: 6px; margin: 6px 0; }}
    .win32-lcd-screen {{ background: #15803d; border: 3px solid #14532d; padding: 4px; }}
    .win32-lcd-grid {{ display: grid; grid-template-columns: repeat(16, 18px); grid-template-rows: repeat(2, 24px); gap: 2px; }}
    .win32-lcd-cell {{ background: #22c55e; border: 1px solid #16a34a; display: flex; align-items: center; justify-content: center; font-family: monospace; font-size: 13px; font-weight: bold; color: #052e16; }}
    .transfer-card {{ margin: 6px 0; border: 1px solid #adadad; padding: 8px; background: #f9f9f9; }}
    .transfer-header, .transfer-meta-text {{ display: flex; justify-content: space-between; }}
    .progress-bar-bg {{ background: #ddd; height: 10px; margin: 6px 0; }} .progress-bar-fill {{ background: #06b025; height: 100%; width: 0%; }}
    .safety-alert, .transfer-unavailable {{ color: #a00; margin: 4px 0; }}
    .win32-bottom-pane {{ border-top: 1px solid #adadad; padding: 6px 12px; display: flex; flex-direction: column; gap: 6px; }}
    .win32-bottom-bar {{ display: flex; justify-content: space-between; align-items: center; }}
    .win32-log-textarea {{ width: 100%; height: 140px; background: #fff; border: 1px solid #7a7a7a; font-family: Consolas, 'Courier New', monospace; font-size: 11px; padding: 4px; }}
    #toast {{ position: fixed; bottom: 10px; right: 10px; background: #ffffe1; border: 1px solid #000; padding: 6px 10px; display: none; }}
  </style>
</head>
<body>
  <div class="win32-window">
    <div class="win32-topbar">
      <div><strong>{identity["name"]}</strong> &nbsp; Port: <span id="connectionStatus">{_esc(status_label)} ({spec.serial_config.baudrate} bps)</span></div>
      <div><button type="button" class="win32-btn" data-action="refresh">Read all</button>
        <label><input type="checkbox" data-action="auto-refresh"> Auto refresh</label></div>
    </div>
    <div class="win32-tab-bar">{"".join(tab_buttons)}</div>
    <div class="win32-workspace">{"".join(tab_panes)}</div>
    <div class="win32-bottom-pane">
      <div class="win32-bottom-bar">
        <div><button type="button" class="win32-btn" id="btn-clear-log">Clear Text</button>
          <label><input type="checkbox" id="chk-log-payloads" checked /> Log Payloads</label></div>
        <button type="button" class="win32-btn" id="btn-stop-log">Stop</button>
      </div>
      <textarea class="win32-log-textarea" id="win32-log-output" readonly placeholder="Waiting for serial port activity..."></textarea>
    </div>
  </div>
  <div id="toast"></div>
  <script type="application/json" id="dashboard-config">{_json_for_script(config)}</script>
  <script>{_RUNTIME_SCRIPT}</script>
</body>
</html>
"""


# Shared page runtime. Kept out of the f-strings above so its braces need no doubling.
_RUNTIME_SCRIPT = r"""
(function() {
  'use strict';
  const cfg = JSON.parse(document.getElementById('dashboard-config').textContent);
  const api = encodeURIComponent(cfg.api);
  const history = {};          // field -> recent numeric values for sparklines
  let seenExchange = null;     // newest exchange already written to the logs
  let logPaused = false;
  let autoTimer = null;

  function toast(text, isError) {
    const el = document.getElementById('toast');
    el.textContent = text;
    el.className = isError ? 'error' : '';
    el.style.display = 'block';
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.style.display = 'none'; }, 5000);
  }

  async function call(method, url, body) {
    const res = await fetch(url, {method, headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
    let data = null;
    try { data = await res.json(); } catch (e) { /* not JSON */ }
    return {status: res.status, ok: res.ok, data: data || {}};
  }

  function fmt(v) {
    if (typeof v === 'number' && !Number.isInteger(v)) return v.toFixed(2);
    if (v === null || v === undefined) return '--';
    if (typeof v === 'object') return JSON.stringify(v);
    return String(v);
  }

  // ------------------------------------------------------------ state
  function latest(fields) {
    const out = {};
    for (const s of Object.values(fields)) {
      const cur = out[s.field_name];
      if (!cur || s.age_s < cur.age_s) out[s.field_name] = s;
    }
    return out;
  }

  function renderState(snap) {
    const conn = snap.connection || {};
    const badge = document.getElementById('connectionStatus');
    const where = conn.connected ? (conn.simulated ? 'SIMULATED' : conn.port) : '';
    badge.textContent = (conn.connected ? 'CONNECTED' : 'DISCONNECTED') + (where ? ' ' + where : '') + ' (' + (conn.baudrate || cfg.baudrate) + ' bps)' + (conn.read_only ? ' read-only' : '');
    badge.className = badge.className.replace(/status-(dis)?connected/g, '') + (conn.connected ? ' status-connected' : ' status-disconnected');

    const values = latest(((snap.state || {}).fields) || {});
    document.querySelectorAll('[data-field]').forEach(el => {
      const s = values[el.getAttribute('data-field')];
      const quality = s ? s.quality : 'none';
      el.classList.remove('q-good', 'q-stale', 'q-offline', 'q-none');
      el.classList.add('q-' + quality);
      el.title = s ? (quality + ', ' + s.age_s + ' s old') : 'no value received yet';
      if (el.classList.contains('gauge-bar-fill')) {
        const lo = parseFloat(el.dataset.min), hi = parseFloat(el.dataset.max);
        const pct = s && typeof s.value === 'number' && hi > lo ? Math.max(0, Math.min(100, (s.value - lo) / (hi - lo) * 100)) : 0;
        el.style.width = pct + '%';
      } else if (el.tagName.toLowerCase() === 'svg') {
        if (s && typeof s.value === 'number') {
          const h = history[el.dataset.field] = history[el.dataset.field] || [];
          if (h.length === 0 || h[h.length - 1].t !== s.timestamp) h.push({t: s.timestamp, v: s.value});
          while (h.length > 40) h.shift();
          const vals = h.map(p => p.v), lo = Math.min(...vals), hi = Math.max(...vals), span = (hi - lo) || 1;
          el.querySelector('polyline').setAttribute('points', h.map((p, i) => (i * 120 / Math.max(1, h.length - 1)).toFixed(1) + ',' + (28 - (p.v - lo) / span * 26).toFixed(1)).join(' '));
        }
      } else {
        el.textContent = s ? fmt(s.value) : '--';
      }
    });
    document.querySelectorAll('[data-lcd-field]').forEach(grid => {
      const s = values[grid.getAttribute('data-lcd-field')];
      const text = s ? String(s.value).padEnd(32, ' ').slice(0, 32) : ''.padEnd(32, ' ');
      grid.querySelectorAll('.win32-lcd-cell').forEach((cell, i) => { cell.textContent = text[i]; });
    });

    renderTraffic(snap.exchanges || []);
    const cj = document.getElementById('connectionJson'); if (cj) cj.textContent = JSON.stringify(conn, null, 2);
    const sj = document.getElementById('stateJson'); if (sj) sj.textContent = JSON.stringify(snap.state, null, 2);
  }

  function renderTraffic(exchanges) {
    const rows = document.getElementById('engineerRows');
    if (rows && exchanges.length) {
      rows.replaceChildren();
      exchanges.forEach(ex => {
        const tr = document.createElement('tr');
        const crc = ex.crc_valid === null ? '–' : (ex.crc_valid ? '✓' : '✗');
        [ex.command_name, ex.status, ex.latency_ms + ' ms', crc, ex.request_raw_hex, ex.response_raw_hex || '(none)'].forEach((text, i) => {
          const td = document.createElement('td');
          td.textContent = text;
          if (i >= 4) td.className = 'hex';
          if (i === 1) td.className = ex.status === 'ok' ? 'ok' : 'bad';
          tr.appendChild(td);
        });
        tr.addEventListener('click', () => {
          const d = document.getElementById('engineerDetail');
          d.hidden = false;
          d.textContent = JSON.stringify({request: ex.request_field_slices, response: ex.response_field_slices, error: ex.error}, null, 2);
        });
        rows.appendChild(tr);
      });
    }
    // Append exchanges newer than the last one logged, oldest first
    const fresh = [];
    for (const ex of exchanges) { if (ex.exchange_id === seenExchange) break; fresh.push(ex); }
    if (exchanges.length) seenExchange = exchanges[0].exchange_id;
    if (logPaused || !fresh.length) return;
    const payloads = !document.getElementById('chk-log-payloads') || document.getElementById('chk-log-payloads').checked;
    const lines = fresh.reverse().map(ex => {
      const when = new Date(ex.timestamp * 1000).toLocaleTimeString();
      const head = when + ' ' + ex.command_name + ' ' + ex.status + ' ' + ex.latency_ms + ' ms';
      return payloads ? head + '\n  TX ' + ex.request_raw_hex + '\n  RX ' + (ex.response_raw_hex || '(none)') : head;
    });
    const raw = document.getElementById('rawLog');
    if (raw) raw.textContent = (raw.textContent === 'No frames yet.' ? '' : raw.textContent + '\n') + lines.join('\n');
    const w32 = document.getElementById('win32-log-output');
    if (w32) { w32.value += lines.join('\n') + '\n'; w32.scrollTop = w32.scrollHeight; }
  }

  async function poll() {
    try {
      const r = await call('GET', '/api/device/' + api + '/state');
      if (r.ok) renderState(r.data);
    } catch (e) {
      const badge = document.getElementById('connectionStatus');
      badge.textContent = 'NO SERVER (' + cfg.baudrate + ' bps)';
    }
  }

  async function refresh() {
    const r = await call('POST', '/api/device/' + api + '/refresh');
    if (r.ok) renderState(r.data); else toast(r.data.detail || ('Read failed: HTTP ' + r.status), true);
  }

  // ------------------------------------------------------------ commands
  function paramValue(el) {
    if (el.type === 'checkbox') return el.checked;
    const v = el.value;
    const t = el.dataset.type || '';
    if (v === '') return undefined;
    if (/^(u?int|float|enum)/.test(t) && !isNaN(Number(v))) return Number(v);
    return v;
  }

  async function sendCommand(name) {
    const meta = cfg.commands[name] || {};
    const params = {};
    document.querySelectorAll('[data-param][data-command="' + CSS.escape(name) + '"]').forEach(el => {
      const v = paramValue(el);
      if (v !== undefined) params[el.dataset.param] = v;
    });
    if (meta.confirm) {
      const text = meta.warning || ("'" + name + "' is " + meta.safety + ' and changes the device. Send it?');
      if (!window.confirm(text)) return;
    }
    const r = await call('POST', '/api/send/' + api, {command: name, params, confirm: !!meta.confirm});
    if (r.ok) toast(name + ': OK (' + r.data.latency_ms + ' ms)');
    else toast(name + ': ' + (r.data.error || r.data.detail || ('HTTP ' + r.status)), true);
    poll();
  }

  // ------------------------------------------------------------ transfers
  function readBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  function setTransfer(card, job) {
    const p = job.progress || {};
    card.querySelector('.progress-bar-fill').style.width = (p.percent_complete || 0) + '%';
    card.querySelector('.transfer-progress').textContent = (p.percent_complete || 0).toFixed(1) + '% | ' + ((p.transfer_rate_bps || 0) / 1024).toFixed(1) + ' kB/s | chunk ' + (p.current_chunk || 0) + '/' + (p.total_chunks || 0);
    card.querySelector('.transfer-eta').textContent = job.done ? 'ETA: --' : 'ETA: ' + Math.ceil(p.estimated_remaining_seconds || 0) + ' s';
    let state = String(job.state || '').toUpperCase();
    if (job.done && job.state === 'completed') state = job.committed ? 'COMMITTED' : 'TRANSFERRED (NOT COMMITTED)';
    card.querySelector('.transfer-state').textContent = state;
    const msg = card.querySelector('.transfer-message');
    msg.textContent = job.error || (job.done && job.state === 'completed' && !job.committed ? 'All chunks were acknowledged, but the device was not asked to commit the file.' : '');
    msg.className = 'transfer-message ' + (job.error ? 'bad' : (job.committed ? 'ok' : ''));
    card.querySelector('[data-action="start-transfer"]').disabled = !job.done;
    card.querySelector('[data-action="cancel-transfer"]').disabled = !!job.done;
    card.querySelector('[data-action="retry-transfer"]').disabled = !(job.done && job.state !== 'completed');
  }

  async function startTransfer(card) {
    const input = card.querySelector('.file-input');
    const file = input.files && input.files[0];
    if (!file) { toast('Select a file to transfer first.', true); return; }
    const accept = (card.dataset.accept || '').split(',').filter(Boolean).map(s => s.toLowerCase());
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (accept.length && !accept.includes(ext)) { toast(file.name + ' is not one of ' + accept.join(', '), true); return; }
    const maxSize = parseInt(card.dataset.maxSize || '0', 10);
    if (maxSize > 0 && file.size > maxSize) { toast('File is ' + file.size + ' bytes; the maximum is ' + maxSize, true); return; }
    let confirmed = false;
    if (card.dataset.destructive === 'true' || card.dataset.prompt) {
      if (!window.confirm(card.dataset.prompt || 'This transfer changes the device. Continue?')) return;
      confirmed = true;
    }
    const body = {widget_ref: card.dataset.transferRef, file_name: file.name, data_base64: await readBase64(file), confirm: confirmed};
    let r = await call('POST', '/api/device/' + api + '/transfer', body);
    if (r.status === 428 && window.confirm(r.data.detail || 'This transfer changes the device. Continue?')) {
      body.confirm = true;
      r = await call('POST', '/api/device/' + api + '/transfer', body);
    }
    if (!r.ok) { toast(r.data.detail || ('Transfer refused: HTTP ' + r.status), true); return; }
    card.dataset.job = r.data.job_id;
    setTransfer(card, r.data);
    const timer = setInterval(async () => {
      const s = await call('GET', '/api/device/' + api + '/transfer/' + encodeURIComponent(card.dataset.job));
      if (s.ok) setTransfer(card, s.data);
      if (!s.ok || s.data.done) { clearInterval(timer); poll(); }
    }, 400);
  }

  // ------------------------------------------------------------ events
  document.addEventListener('input', e => {
    if (e.target.matches('input[type=range]')) {
      const out = e.target.parentElement.querySelector('.slider-value');
      if (out) out.textContent = e.target.value;
    }
  });

  document.addEventListener('click', e => {
    const t = e.target.closest('button, input[type=checkbox][data-action]');
    if (!t) return;
    if (t.matches('.mode-tab')) {
      document.querySelectorAll('.mode-tab').forEach(x => x.classList.toggle('active', x === t));
      document.querySelectorAll('.mode-view').forEach(v => v.classList.toggle('active', v.id === t.dataset.mode + 'View'));
    } else if (t.matches('.win32-tab-button')) {
      document.querySelectorAll('.win32-tab-button').forEach(x => x.classList.toggle('active', x === t));
      document.querySelectorAll('.win32-tab-pane').forEach(p => p.classList.toggle('active', p.dataset.pane === t.dataset.tab));
    } else if (t.dataset.role === 'command') {
      sendCommand(t.dataset.command);
    } else if (t.dataset.action === 'refresh') {
      refresh();
    } else if (t.dataset.action === 'auto-refresh') {
      clearInterval(autoTimer);
      autoTimer = t.checked ? setInterval(refresh, 2000) : null;
    } else if (t.dataset.action === 'start-transfer' || t.dataset.action === 'retry-transfer') {
      startTransfer(t.closest('.transfer-card'));
    } else if (t.dataset.action === 'cancel-transfer') {
      const card = t.closest('.transfer-card');
      if (card.dataset.job) call('POST', '/api/device/' + api + '/transfer/' + encodeURIComponent(card.dataset.job) + '/cancel');
    } else if (t.id === 'btn-clear-log') {
      document.getElementById('win32-log-output').value = '';
    } else if (t.id === 'btn-stop-log') {
      logPaused = !logPaused;
      t.textContent = logPaused ? 'Resume' : 'Stop';
    }
  });

  poll();
  setInterval(() => { if (!document.hidden) poll(); }, 1000);
})();
"""
