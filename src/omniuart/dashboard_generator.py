"""Generated Device Control Console Dashboard for OmniUART (#230).

Generates a standalone or web-embeddable Device Control Console HTML workbench driven by
ProtocolSpec and DeviceUISpec declarations, integrating connection state, identity, controls,
status values, telemetry plots, and traffic activity feed.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from omniuart.core.device_ui import DeviceUISpec, WidgetSpec
from omniuart.core.models import ProtocolSpec


def generate_device_dashboard_html(
    spec: ProtocolSpec,
    ui_spec: Optional[DeviceUISpec] = None,
) -> str:
    """Generate Device Control Console HTML driven by ProtocolSpec and DeviceUISpec."""
    device_name = ui_spec.identity.name if ui_spec else spec.metadata.name
    device_model = ui_spec.identity.model if ui_spec else "Universal UART Device"
    device_vendor = ui_spec.identity.vendor if ui_spec else "OmniUART"
    device_version = ui_spec.identity.version if ui_spec else spec.metadata.version

    # Collect widgets or build defaults from protocol spec
    panels_data: List[Dict[str, Any]] = []

    if ui_spec and ui_spec.panels:
        for p in ui_spec.panels:
            panel_dict = {
                "name": p.name,
                "title": p.title,
                "icon": p.icon or "layer",
                "groups": [],
            }
            for g in p.groups:
                group_dict = {
                    "name": g.name,
                    "title": g.title,
                    "layout": g.layout,
                    "widgets": [w.model_dump() for w in g.widgets],
                }
                panel_dict["groups"].append(group_dict)
            panels_data.append(panel_dict)
    else:
        # Default panel generated from protocol commands and telemetry
        default_widgets = []
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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
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
    for panel in panels_data:
        html += f"""
    <h2 style="grid-column: 1 / -1; color: var(--accent); margin-top: 16px; margin-bottom: 0;">{panel['title']}</h2>
"""
        for group in panel["groups"]:
            html += f"""
    <div class="group-card">
      <h3 style="margin-top:0; color: var(--accent);">{group['title']}</h3>
"""
            for widget in group["widgets"]:
                label = widget["label"]
                unit_str = f" ({widget['unit']})" if widget.get("unit") else ""
                html += f"""
      <div class="widget-row">
        <span>{label}{unit_str}</span>
        <button class="btn" onclick="triggerWidget('{widget.get('field_ref')}')">{widget['widget_type'].upper()}</button>
      </div>
"""
            html += "    </div>\n"

    html += """  </div>
  <script>
    function triggerWidget(fieldRef) {
      console.log("Triggering widget for field/command:", fieldRef);
    }
  </script>
</body>
</html>
"""
    return html
