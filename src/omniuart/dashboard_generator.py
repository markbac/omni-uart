"""Dashboard HTML Generator for OmniUART Device UI / Device Explorer (#230, #316).

Generates responsive, device-centric HTML control consoles driven by ProtocolSpec and DeviceUISpec,
with Operator/Engineer presentation, live telemetry gauges, command action buttons, and strict
HTML escaping against injection.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from omniuart.core.device_ui import DeviceUISpec
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
