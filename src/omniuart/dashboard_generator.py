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
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="device-title">⚡ {device_name} ({device_model})</div>
      <div style="color: #94a3b8; font-size: 0.9rem;">Vendor: {device_vendor} | Firmware: {device_version}</div>
    </div>
    <div>
      <span class="status-badge" id="connectionStatus">CONNECTED (115200 bps)</span>
    </div>
  </div>

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
                label = html.escape(str(widget.get("label") or ""))
                unit = widget.get("unit")
                unit_str = f" ({html.escape(str(unit))})" if unit else ""
                field_ref = html.escape(str(widget.get("field_ref") or ""))
                widget_type = html.escape(str(widget.get("widget_type") or "BUTTON").upper())
                html_parts.append(f"""      <div class="widget-row">
        <span>{label}{unit_str}</span>
        <button class="btn" data-field-ref="{field_ref}">{widget_type}</button>
      </div>
""")
            html_parts.append("    </div>\n")

    html_parts.append("""  </div>
  <script>
    document.addEventListener("click", function(e) {
      if (e.target && e.target.matches("button[data-field-ref]")) {
        var ref = e.target.getAttribute("data-field-ref");
        console.log("Triggering widget for field/command:", ref);
      }
    });
  </script>
</body>
</html>
""")

    return "".join(html_parts)
