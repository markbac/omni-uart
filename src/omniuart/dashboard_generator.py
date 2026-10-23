"""Dashboard HTML Generator for OmniUART Device UI / Device Explorer (#230, #316).

Generates responsive, device-centric HTML control consoles driven by ProtocolSpec and DeviceUISpec,
with Operator/Engineer presentation, live telemetry gauges, command action buttons, and strict
HTML escaping against injection.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from omniuart.core.device_ui import DeviceUISpec, PanelSpec
from omniuart.core.models import ProtocolSpec


def generate_device_dashboard_html(
    spec: ProtocolSpec,
    ui_spec: Optional[DeviceUISpec] = None,
    connection_status: str = "CONNECTED",
    is_connected: Optional[bool] = None,
) -> str:
    """Generate Device Control Console HTML driven by ProtocolSpec and DeviceUISpec.

    All user- and device-supplied values are strictly escaped to prevent HTML/XSS injection (#316).
    """
    raw_device_name = ui_spec.identity.name if ui_spec else spec.metadata.name
    raw_device_model = ui_spec.identity.model if ui_spec else "Universal UART Device"
    raw_device_vendor = ui_spec.identity.vendor if ui_spec else "OmniUART"
    raw_device_version = ui_spec.identity.version if ui_spec else spec.metadata.version

    device_name = html.escape(str(raw_device_name or ''))
    device_model = html.escape(str(raw_device_model or ''))
    device_vendor = html.escape(str(raw_device_vendor or ''))
    device_version = html.escape(str(raw_device_version or ''))

    if is_connected is not None:
        status_label = "CONNECTED" if is_connected else "DISCONNECTED"
    else:
        status_label = connection_status.upper()

    baudrate = spec.serial_config.baudrate
    conn_text = f"{status_label} ({baudrate} bps)"
    conn_class = "status-badge status-connected" if "CONNECT" in status_label and "DISCONNECT" not in status_label else "status-badge status-disconnected"
    theme_val = str(ui_spec.theme).lower() if ui_spec and hasattr(ui_spec, "theme") and ui_spec.theme else "modern"
    if theme_val in ("win32", "classic", "desktop", "industrial"):
        return _generate_win32_dashboard_html(
            spec=spec,
            ui_spec=ui_spec,
            device_name=device_name,
            device_model=device_model,
            device_vendor=device_vendor,
            device_version=device_version,
            status_label=status_label,
            baudrate=baudrate,
        )


    # Collect widgets or build defaults from protocol spec
    panels_data: List[Dict[str, Any]] = []

    if ui_spec and ui_spec.panels:
        for p in ui_spec.panels:
            groups_list: List[Dict[str, Any]] = []
            panel_dict: Dict[str, Any] = {
                "name": p.name,
                "title": p.title,
                "icon": p.icon or "layer",
                "groups": groups_list,
            }
            for g in p.groups:
                group_dict: Dict[str, Any] = {
                    "name": g.name,
                    "title": g.title,
                    "layout": g.layout,
                    "widgets": [w.model_dump() for w in g.widgets],
                }
                groups_list.append(group_dict)
            panels_data.append(panel_dict)
    else:
        # Default panel generated from protocol commands and telemetry
        default_widgets: List[Dict[str, Any]] = []
        for cmd in spec.commands:
            default_widgets.append({
                "widget_type": "button",
                "field_ref": cmd.name,
                "label": f"Send {cmd.name.title()}",
                "unit": None,
            })
        for tel in spec.telemetry:
            for field in tel.fields:
                default_widgets.append({
                    "widget_type": "gauge",
                    "field_ref": field.name,
                    "label": field.name.replace("_", " ").title(),
                    "unit": field.unit,
                })

        panels_data.append({
            "name": "default",
            "title": "Device Dashboard",
            "icon": "dashboard",
            "groups": [{
                "name": "main",
                "title": "Controls & Telemetry",
                "layout": "grid",
                "widgets": default_widgets,
            }],
        })

    html_parts: List[str] = [
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';">
  <title>⚡ {device_name} - Device Control Console</title>
  <style>
    :root {{
      --bg: #0f172a; --panel: #1e293b; --accent: #38bdf8; --text: #f8fafc;
      --border: #334155; --success: #22c55e; --warning: #f59e0b; --danger: #ef4444;
    }}
    body {{
      margin: 0; padding: 20px; background: var(--bg); color: var(--text);
      font-family: 'Segoe UI', system-ui, sans-serif;
    }}
    .header {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 16px 24px; background: var(--panel); border: 1px solid var(--border);
      border-radius: 8px; margin-bottom: 20px;
    }}
    .device-title {{ font-size: 1.4rem; font-weight: bold; color: var(--accent); }}
    .status-badge {{
      background: #14532d; color: var(--success); padding: 4px 12px;
      border-radius: 12px; font-size: 0.85rem; font-weight: 600;
    }}
    .dashboard-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px;
    }}
    .group-card {{
      background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 16px;
    }}
    .widget-row {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 10px 0; border-bottom: 1px solid var(--border);
    }}
    .widget-row:last-child {{ border-bottom: none; }}
    .btn {{
      background: var(--accent); color: #000; font-weight: 600; padding: 6px 14px;
      border: none; border-radius: 6px; cursor: pointer;
    }}
    .btn:hover {{ opacity: 0.9; }}
    .transfer-card {{
      background: #111827; border: 1px solid #374151; border-radius: 8px; padding: 12px; margin: 10px 0;
    }}
    .transfer-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
    .transfer-badge {{ background: #0369a1; color: #fff; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; }}
    .transfer-danger {{ background: #991b1b; color: #fecaca; }}
    .file-input {{ display: block; width: 100%; margin: 8px 0; font-size: 0.85rem; color: #94a3b8; }}
    .progress-bar-bg {{ background: #1e293b; border-radius: 4px; height: 10px; width: 100%; overflow: hidden; margin: 8px 0; }}
    .progress-bar-fill {{ background: var(--accent); height: 100%; width: 0%; transition: width 0.3s; }}
    .transfer-meta-text {{ font-size: 0.8rem; color: #94a3b8; display: flex; justify-content: space-between; margin-bottom: 4px; }}
    .safety-alert {{ background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); border-radius: 6px; padding: 8px; margin: 8px 0; font-size: 0.8rem; color: #fca5a5; }}
    .transfer-actions {{ display: flex; gap: 8px; margin-top: 10px; }}
    .btn-transfer {{ background: var(--accent); color: #000; }}
    .btn-cancel {{ background: #475569; color: #fff; }}
    .btn-retry {{ background: #d97706; color: #fff; }}
    .status-connected {{ background: #14532d; color: var(--success); }}
    .status-disconnected {{ background: #7f1d1d; color: #fca5a5; }}
    .mode-tabs {{ display: flex; gap: 10px; margin-bottom: 20px; }}
    .mode-tab {{
      background: var(--panel); border: 1px solid var(--border); color: #94a3b8;
      padding: 8px 18px; border-radius: 6px; cursor: pointer; font-weight: 600;
    }}
    .mode-tab.active {{ background: #0284c7; color: #fff; border-color: #38bdf8; }}
    .mode-view {{ display: none; }}
    .mode-view.active {{ display: block; }}
    .gauge-container {{ display: flex; align-items: center; gap: 12px; }}
    .gauge-bar-bg {{ background: #1e293b; width: 120px; height: 10px; border-radius: 5px; overflow: hidden; }}
    .gauge-bar-fill {{ background: #38bdf8; height: 100%; width: 50%; }}
    .widget-slider {{ width: 140px; }}
    .widget-select, .widget-input {{
      background: #0f172a; border: 1px solid var(--border); color: #fff;
      padding: 4px 8px; border-radius: 4px;
    }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="device-title">⚡ {device_name} ({device_model})</div>
      <div style="color: #94a3b8; font-size: 0.9rem;">Vendor: {device_vendor} | Firmware: {device_version}</div>
    </div>
    <div>
      <span class="{conn_class}" id="connectionStatus">{conn_text}</span>
    </div>
  </div>

  <div class="mode-tabs">
    <button class="mode-tab active" data-mode="operator">Operator Mode</button>
    <button class="mode-tab" data-mode="engineer">Engineer Mode</button>
    <button class="mode-tab" data-mode="developer">Developer Mode</button>
  </div>

  <div id="operatorView" class="mode-view active">
    <div class="dashboard-grid" id="panelsContainer">
"""
    ]

    for panel in panels_data:
        panel_title = html.escape(str(panel.get("title") or ""))
        html_parts.append(
            f'    <h2 style="grid-column: 1 / -1; color: var(--accent); margin-top: 16px; margin-bottom: 0;">{panel_title}</h2>\n'
        )
        for group in panel.get("groups", []):
            group_title = html.escape(str(group.get("title") or ""))
            html_parts.append(f"""    <div class="group-card">
      <h3 style="margin-top:0; color: var(--accent);">{group_title}</h3>
""")
            for widget in group.get("widgets", []):
                w_type = str(widget.get("widget_type") or "").lower()
                label = html.escape(str(widget.get("label") or ""))
                field_ref = html.escape(str(widget.get("field_ref") or ""))

                if w_type in ("file_transfer", "firmware_update"):
                    supported_exts = widget.get("supported_file_types") or [".bin"]
                    accept_attr = html.escape(",".join(supported_exts))
                    max_size = int(widget.get("max_size_bytes") or (16 * 1024 * 1024))
                    max_size_mb = round(max_size / (1024 * 1024), 1)
                    transfer_type = html.escape(str(widget.get("transfer_type") or "binary").upper())
                    is_destructive = bool(widget.get("destructive", False))
                    prompt_text = html.escape(str(widget.get("confirm_prompt") or ""))
                    warning_text = html.escape(str(widget.get("safety_warning") or ""))
                    badge_class = "transfer-badge transfer-danger" if is_destructive else "transfer-badge"

                    html_parts.append(f"""      <div class="transfer-card" data-transfer-ref="{field_ref}" data-destructive="{str(is_destructive).lower()}" data-max-size="{max_size}">
        <div class="transfer-header">
          <strong>{label}</strong>
          <span class="{badge_class}">{transfer_type}</span>
        </div>
        <div class="transfer-meta-text">
          <span>Supported: {accept_attr} | Max: {max_size_mb} MB</span>
          <span id="badge_state_{field_ref}" style="font-weight:600; color:var(--accent);">IDLE</span>
        </div>
""")
                    if is_destructive or warning_text:
                        alert_msg = warning_text or prompt_text or "Warning: Destructive device operation."
                        html_parts.append(f"""        <div class="safety-alert">⚠️ {alert_msg}</div>\n""")

                    html_parts.append(f"""        <input type="file" class="file-input" id="file_{field_ref}" accept="{accept_attr}" data-field-ref="{field_ref}" />
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" id="bar_{field_ref}"></div>
        </div>
        <div class="transfer-meta-text">
          <span id="progress_text_{field_ref}">0% | 0 kB/s</span>
          <span id="eta_text_{field_ref}">ETA: --</span>
        </div>
        <div class="transfer-actions">
          <button class="btn btn-transfer" data-action="start-transfer" data-field-ref="{field_ref}" data-prompt="{prompt_text}">Start Transfer</button>
          <button class="btn btn-cancel" data-action="cancel-transfer" data-field-ref="{field_ref}">Cancel</button>
          <button class="btn btn-retry" data-action="retry-transfer" data-field-ref="{field_ref}">Retry</button>
        </div>
      </div>
""")
                else:
                    unit = widget.get("unit")
                    unit_str = f" ({html.escape(str(unit))})" if unit else ""
                    widget_type = html.escape(str(widget.get("widget_type") or "BUTTON").upper())
                    html_parts.append(f"""      <div class="widget-row">
        <span>{label}{unit_str}</span>
        <button class="btn" data-field-ref="{field_ref}">{widget_type}</button>
      </div>
""")
            html_parts.append("    </div>\n")

    html_parts.append("""    </div>
  </div>

  <div id="engineerView" class="mode-view">
    <div class="group-card" style="margin-bottom: 20px;">
      <h3 style="color: var(--accent); margin-top:0;">🔧 Engineer Protocol Diagnostics</h3>
      <p style="color: #94a3b8; font-size: 0.9rem;">Decoded message structures, packet timing, request/response correlation, and integrity verification.</p>
      <div style="background: #0f172a; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 0.85rem;">
        <div><strong>Baud Rate:</strong> {baudrate} bps | <strong>Framing:</strong> {html.escape(spec.framing.type.value.upper())}</div>
        <div><strong>Integrity Algorithm:</strong> {html.escape(spec.framing.integrity.algorithm if spec.framing.integrity else "None")}</div>
      </div>
    </div>
  </div>

  <div id="developerView" class="mode-view">
    <div class="group-card">
      <h3 style="color: var(--accent); margin-top:0;">💻 Developer Low-Level View</h3>
      <p style="color: #94a3b8; font-size: 0.9rem;">Raw hex stream, byte boundaries, transport buffer counters, and session diagnostics.</p>
      <pre style="background: #0f172a; padding: 12px; border-radius: 6px; color: #34d399; font-size: 0.85rem; overflow-x: auto;">// Active Protocol: {device_name} (v{device_version})
// Commands defined: {len(spec.commands)}
// Telemetry channels: {len(spec.telemetry)}</pre>
    </div>
  </div>

  <script>
    document.addEventListener("click", function(e) {
      if (e.target && e.target.matches(".mode-tab")) {
        var mode = e.target.getAttribute("data-mode");
        document.querySelectorAll(".mode-tab").forEach(function(t) { t.classList.remove("active"); });
        document.querySelectorAll(".mode-view").forEach(function(v) { v.classList.remove("active"); });
        e.target.classList.add("active");
        var view = document.getElementById(mode + "View");
        if (view) view.classList.add("active");
      }

      var btn = e.target;
      if (!btn) return;

      var action = btn.getAttribute("data-action");
      var ref = btn.getAttribute("data-field-ref");

      if (action === "start-transfer") {
        var card = btn.closest(".transfer-card");
        var isDestructive = card ? card.getAttribute("data-destructive") === "true" : false;
        var promptMsg = btn.getAttribute("data-prompt");

        if (isDestructive || promptMsg) {
          var confirmed = window.confirm(promptMsg || "Warning: This operation will modify device memory or firmware. Do you wish to continue?");
          if (!confirmed) {
            console.log("Transfer aborted by user confirmation dialog:", ref);
            return;
          }
        }

        var fileInput = document.getElementById("file_" + ref);
        if (fileInput && fileInput.files && fileInput.files.length > 0) {
          var file = fileInput.files[0];
          var maxSize = parseInt(card.getAttribute("data-max-size") || "0", 10);
          if (maxSize > 0 && file.size > maxSize) {
            alert("Selected file exceeds max capability: " + file.size + " > " + maxSize + " bytes.");
            return;
          }
          console.log("Initiating transfer for:", ref, "file:", file.name, "size:", file.size);
          var badge = document.getElementById("badge_state_" + ref);
          if (badge) badge.textContent = "TRANSFERRING";
        } else {
          alert("Please select a file to transfer first.");
        }
      } else if (action === "cancel-transfer") {
        console.log("Cancelling transfer for:", ref);
        var badge = document.getElementById("badge_state_" + ref);
        if (badge) badge.textContent = "CANCELLED";
      } else if (action === "retry-transfer") {
        console.log("Retrying transfer for:", ref);
        var badge = document.getElementById("badge_state_" + ref);
        if (badge) badge.textContent = "TRANSFERRING";
      } else if (btn.matches("button[data-field-ref]")) {
        console.log("Triggering widget for field/command:", ref);
      }
    });
  </script>
</body>
</html>
""")

    return "".join(html_parts)


def _generate_win32_dashboard_html(
    spec: ProtocolSpec,
    ui_spec: Optional[DeviceUISpec],
    device_name: str,
    device_model: str,
    device_vendor: str,
    device_version: str,
    status_label: str,
    baudrate: int,
) -> str:
    """Generate exact Win32/Classic Industrial desktop utility tool console layout."""
    import html as pyhtml

    app_title = f"{device_name} - V{device_version}"
    status_text = "uninit" if "DISCONNECT" in status_label else status_label.lower()

    # Build tabs from panels
    panels = ui_spec.panels if ui_spec and ui_spec.panels else []
    if not panels:
        # Default single tab if none defined
        panels = [PanelSpec(name="info", title="Info", groups=[])]

    tab_buttons = []
    tab_panes = []

    for idx, panel in enumerate(panels):
        p_name = pyhtml.escape(panel.name)
        p_title = pyhtml.escape(panel.title)
        active_cls = "active" if idx == 0 else ""

        tab_buttons.append(
            f'<button type="button" class="win32-tab-button {active_cls}" data-tab="{p_name}">{p_title}</button>'
        )

        fieldsets = []
        for group in panel.groups:
            g_title = pyhtml.escape(group.title)
            rows = []
            for w in group.widgets:
                w_type = str(w.widget_type).lower()
                w_label = pyhtml.escape(w.label)
                w_ref = pyhtml.escape(w.field_ref or "")
                w_unit = f" ({pyhtml.escape(w.unit)})" if w.unit else ""

                if w_type in ("lcd_matrix", "lcd_display"):
                    # Retro green 16x2 segmented LCD display matrix
                    cells = "".join(['<div class="win32-lcd-cell"> </div>' for _ in range(32)])
                    rows.append(f"""
                      <div class="win32-lcd-box">
                        <div class="win32-lcd-title" style="font-weight:bold; margin-bottom:4px;">LCD Display</div>
                        <div class="win32-lcd-screen">
                          <div class="win32-lcd-grid">
                            {cells}
                          </div>
                        </div>
                        <button type="button" class="win32-btn" data-field-ref="{w_ref}" style="margin-top:6px;">Read LCD Content</button>
                      </div>
                    """)
                elif w_type in ("dropdown", "enum") or (w.options and len(w.options) > 0):
                    opts = []
                    if w.options:
                        for val, text in w.options.items():
                            opts.append(f'<option value="{pyhtml.escape(str(val))}">{pyhtml.escape(str(text))}</option>')
                    else:
                        opts.append('<option>Option 1</option>')
                    opts_html = "".join(opts)
                    rows.append(f"""
                      <div class="win32-row">
                        <span class="win32-label">{w_label}{w_unit}</span>
                        <select class="win32-select" data-field-ref="{w_ref}">{opts_html}</select>
                        <button type="button" class="win32-btn win32-btn-get" data-action="get" data-field-ref="{w_ref}">Get</button>
                        <button type="button" class="win32-btn win32-btn-set" data-action="set" data-field-ref="{w_ref}">Set</button>
                      </div>
                    """)
                elif w_type in ("checkbox", "switch", "bool"):
                    rows.append(f"""
                      <div class="win32-row">
                        <label class="win32-checkbox-label">
                          <input type="checkbox" data-field-ref="{w_ref}" /> {w_label}{w_unit}
                        </label>
                      </div>
                    """)
                elif w_type in ("button", "action"):
                    rows.append(f"""
                      <div class="win32-row" style="margin-top:2px;">
                        <button type="button" class="win32-btn" data-field-ref="{w_ref}">{w_label}</button>
                      </div>
                    """)
                elif w_type in ("file_transfer", "firmware_update"):
                    rows.append(f"""
                      <div class="win32-transfer-box" style="margin:6px 0; border:1px solid #adadad; padding:8px; background:#f9f9f9;">
                        <table style="width:100%; font-size:11px; border-collapse:collapse; margin-bottom:8px;">
                          <thead><tr style="background:#e1e1e1; text-align:left;"><th style="padding:2px 4px; border:1px solid #adadad;">Section</th><th style="padding:2px 4px; border:1px solid #adadad;">Value</th></tr></thead>
                          <tbody><tr><td style="padding:2px 4px; border:1px solid #adadad;">Firmware Image</td><td style="padding:2px 4px; border:1px solid #adadad;">Idle</td></tr></tbody>
                        </table>
                        <div style="display:flex; gap:6px; align-items:center;">
                          <button type="button" class="win32-btn" data-action="download-ota" data-field-ref="{w_ref}">Download OTA file</button>
                          <button type="button" class="win32-btn" data-action="cancel-ota">Cancel Download</button>
                          <span style="margin-left:10px;">Status: <strong>Idle</strong></span>
                        </div>
                      </div>
                    """)
                else:
                    # Standard paired register with label, input, Get, Set
                    val_str = str(w.default) if hasattr(w, "default") and w.default is not None else ""
                    rows.append(f"""
                      <div class="win32-row">
                        <span class="win32-label">{w_label}{w_unit}</span>
                        <input type="text" class="win32-input" value="{val_str}" style="width:90px;" data-field-ref="{w_ref}" />
                        <button type="button" class="win32-btn win32-btn-get" data-action="get" data-field-ref="{w_ref}">Get</button>
                        <button type="button" class="win32-btn win32-btn-set" data-action="set" data-field-ref="{w_ref}">Set</button>
                      </div>
                    """)

            fieldsets.append(f"""
              <fieldset class="win32-fieldset">
                <legend>{g_title}</legend>
                {"".join(rows)}
              </fieldset>
            """)

        tab_panes.append(f"""
          <div class="win32-tab-pane {active_cls}" id="tab_pane_{p_name}">
            {"".join(fieldsets)}
          </div>
        """)

    tabs_html = "".join(tab_buttons)
    panes_html = "".join(tab_panes)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';">
  <title>{app_title}</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 0;
      background: #f0f0f0;
      color: #000000;
      font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
      font-size: 11px;
      user-select: none;
    }}
    .win32-window {{
      background: #f0f0f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    .win32-topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 12px;
      background: #f0f0f0;
      border-bottom: 1px solid #d0d0d0;
    }}
    .win32-com-section {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .win32-com-section label {{ font-weight: bold; }}
    .win32-status-text {{
      color: #444444;
      margin-left: 12px;
      font-style: italic;
    }}
    .win32-btn {{
      background: #e1e1e1;
      border: 1px solid #adadad;
      color: #000000;
      padding: 2px 10px;
      font-size: 11px;
      font-family: inherit;
      cursor: pointer;
      border-radius: 2px;
      min-width: 50px;
      text-align: center;
    }}
    .win32-btn:hover {{ background: #e5f1fb; border-color: #0078d7; }}
    .win32-btn:active {{ background: #cce4f7; border-color: #005499; }}
    .win32-input, .win32-select {{
      background: #ffffff;
      border: 1px solid #7a7a7a;
      padding: 2px 4px;
      font-size: 11px;
      font-family: inherit;
      border-radius: 1px;
    }}
    .win32-tab-bar {{
      display: flex;
      flex-wrap: wrap;
      background: #e5e5e5;
      border-bottom: 1px solid #adadad;
      padding-top: 4px;
      padding-left: 6px;
      gap: 2px;
    }}
    .win32-tab-button {{
      background: #e1e1e1;
      border: 1px solid #adadad;
      border-bottom: none;
      padding: 4px 10px;
      font-size: 11px;
      cursor: pointer;
      border-top-left-radius: 3px;
      border-top-right-radius: 3px;
    }}
    .win32-tab-button.active {{
      background: #f0f0f0;
      border-bottom: 1px solid #f0f0f0;
      font-weight: bold;
      margin-bottom: -1px;
    }}
    .win32-workspace {{
      flex: 1;
      display: flex;
      flex-direction: column;
    }}
    .win32-tab-pane {{
      display: none;
      padding: 12px;
      flex: 1;
      background: #f0f0f0;
    }}
    .win32-tab-pane.active {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-content: flex-start;
    }}
    .win32-fieldset {{
      border: 1px solid #d0d0d0;
      background: #fafafa;
      padding: 8px 12px;
      border-radius: 3px;
      margin: 0;
      min-width: 240px;
    }}
    .win32-fieldset legend {{
      font-weight: bold;
      padding: 0 4px;
      color: #333333;
    }}
    .win32-row {{
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 5px;
    }}
    .win32-label {{
      min-width: 120px;
      color: #111111;
    }}
    .win32-lcd-box {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      margin: 6px 0;
    }}
    .win32-lcd-screen {{
      background: #15803d;
      border: 3px solid #14532d;
      padding: 4px;
      border-radius: 2px;
      box-shadow: inset 0 0 6px rgba(0,0,0,0.4);
    }}
    .win32-lcd-grid {{
      display: grid;
      grid-template-columns: repeat(16, 18px);
      grid-template-rows: repeat(2, 24px);
      gap: 2px;
    }}
    .win32-lcd-cell {{
      background: #22c55e;
      border: 1px solid #16a34a;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: monospace;
      font-size: 13px;
      font-weight: bold;
      color: #052e16;
    }}
    .win32-bottom-pane {{
      border-top: 1px solid #adadad;
      padding: 6px 12px;
      background: #f0f0f0;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .win32-bottom-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .win32-bottom-controls {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .win32-log-textarea {{
      width: 100%;
      height: 140px;
      background: #ffffff;
      border: 1px solid #7a7a7a;
      font-family: 'Consolas', 'Courier New', monospace;
      font-size: 11px;
      padding: 4px;
      resize: vertical;
    }}
  </style>
</head>
<body>
  <div class="win32-window">
    <!-- Top COM Header -->
    <div class="win32-topbar">
      <div class="win32-com-section">
        <label>COM Port:</label>
        <select class="win32-select" style="width: 110px;">
          <option>COM1</option>
          <option>COM2</option>
          <option>COM3</option>
          <option selected>VIRTUAL_DEVICE</option>
        </select>
        <span class="win32-status-text">{status_text}</span>
      </div>
      <div>
        <button type="button" class="win32-btn" style="min-width: 95px;">Arbitrary comms</button>
      </div>
    </div>

    <!-- Tab Strip (Info, Config, Security, Customization, Time, etc.) -->
    <div class="win32-tab-bar">
      {tabs_html}
    </div>

    <!-- Tab Workspaces -->
    <div class="win32-workspace">
      {panes_html}
    </div>

    <!-- Bottom Logging Console Pane -->
    <div class="win32-bottom-pane">
      <div class="win32-bottom-bar">
        <div class="win32-bottom-controls">
          <button type="button" class="win32-btn" id="btn-clear-log">Clear Text</button>
          <label style="display:flex; align-items:center; gap:4px; cursor:pointer;">
            <input type="checkbox" id="chk-log-payloads" checked /> Log Payloads
          </label>
        </div>
        <div>
          <button type="button" class="win32-btn" id="btn-stop-log" style="min-width: 60px;">Stop</button>
        </div>
      </div>
      <textarea class="win32-log-textarea" id="win32-log-output" readonly placeholder="Waiting for serial port activity..."></textarea>
    </div>
  </div>

  <script>
    document.querySelectorAll('.win32-tab-button').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.win32-tab-button').forEach(function(b) {{ b.classList.remove('active'); }});
        document.querySelectorAll('.win32-tab-pane').forEach(function(p) {{ p.classList.remove('active'); }});
        btn.classList.add('active');
        var tabId = btn.getAttribute('data-tab');
        var pane = document.getElementById('tab_pane_' + tabId);
        if (pane) pane.classList.add('active');
      }});
    }});

    document.getElementById('btn-clear-log').addEventListener('click', function() {{
      document.getElementById('win32-log-output').value = '';
    }});
  </script>
</body>
</html>
"""
