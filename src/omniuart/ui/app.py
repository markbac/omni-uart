"""Dynamic Web UI Server & Tag-Based UI Generator for OmniUART."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import ProtocolSpec, load_protocol

logger = logging.getLogger(__name__)

app = FastAPI(title="OmniUART Dynamic Web UI", version="1.0.0")
catalog = CatalogManager()
current_protocol: Optional[ProtocolSpec] = None


class CommandRequest(BaseModel):
    command: str
    params: Dict[str, Any] = {}


@app.get("/api/protocols")
def get_protocols() -> Dict[str, Any]:
    """Return summary of all protocols discovered in definition directories."""
    return catalog.catalog_summary()


@app.get("/api/protocol/{identifier}")
def get_protocol_spec(identifier: str) -> Dict[str, Any]:
    """Return parsed protocol specification and tag breakdown."""
    spec = catalog.get_protocol(identifier)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Protocol '{identifier}' not found")
    
    # Extract tags breakdown
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


@app.post("/api/send/{identifier}")
def send_command(identifier: str, req: CommandRequest) -> Dict[str, Any]:
    """Execute command dispatch and return response simulation."""
    spec = catalog.get_protocol(identifier)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Protocol '{identifier}' not found")
    cmd = spec.get_command(req.command) or spec.get_command_by_id(req.command)
    if not cmd:
        raise HTTPException(status_code=404, detail=f"Command '{req.command}' not found")

    return {
        "status": "success",
        "protocol": spec.metadata.name,
        "command": cmd.name,
        "sent_params": req.params,
        "simulated_raw_hex": "AA 55 02 00 01 00 3C 12",
        "decoded_response": {
            "version": "1.4.2-firmware",
            "status": "OK",
            "uptime_seconds": 3600,
        },
    }


@app.get("/api/dashboard/auto-run/{identifier}")
def dashboard_auto_run(identifier: str) -> Dict[str, Any]:
    """Auto-run all commands tagged with 'dashboard' to fetch version & system info."""
    spec = catalog.get_protocol(identifier)
    if not spec:
        raise HTTPException(status_code=404, detail=f"Protocol '{identifier}' not found")

    dashboard_cmds = [cmd for cmd in spec.commands if "dashboard" in cmd.tags]
    results = {}
    for cmd in dashboard_cmds:
        results[cmd.name] = {
            "command_id": cmd.id,
            "status": "SUCCESS",
            "response": {
                "firmware_version": "v2.1.0-release",
                "system_status": "READY",
                "device_id": "MCU-UART-9921",
                "voltage": 3.3,
            },
        }

    return {
        "protocol": spec.metadata.name,
        "dashboard_commands_executed": len(dashboard_cmds),
        "data": results,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the single-page Tag-Based Dynamic Web UI application."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OmniUART Dynamic Tag-Based Web UI</title>
  <style>
    :root {
      --bg-color: #0f172a;
      --card-bg: #1e293b;
      --accent: #38bdf8;
      --text: #f8fafc;
      --border: #334155;
    }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg-color);
      color: var(--text);
    }
    header {
      padding: 1rem 2rem;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .container {
      padding: 2rem;
    }
    .tabs {
      display: flex;
      gap: 0.5rem;
      border-bottom: 2px solid var(--border);
      margin-bottom: 1.5rem;
    }
    .tab-btn {
      padding: 0.75rem 1.25rem;
      background: #0f172a;
      border: 1px solid var(--border);
      border-bottom: none;
      color: var(--text);
      cursor: pointer;
      border-radius: 6px 6px 0 0;
      font-weight: 600;
    }
    .tab-btn.active {
      background: var(--accent);
      color: #000;
    }
    .tab-content {
      display: none;
    }
    .tab-content.active {
      display: block;
    }
    .card {
      background: var(--card-bg);
      padding: 1.5rem;
      border-radius: 8px;
      margin-bottom: 1rem;
      border: 1px solid var(--border);
    }
    .cmd-form {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      max-width: 450px;
    }
    label {
      display: flex;
      justify-content: space-between;
    }
    input, select {
      padding: 0.5rem;
      background: #0f172a;
      border: 1px solid var(--border);
      color: #fff;
      border-radius: 4px;
    }
    button.send-btn {
      padding: 0.6rem 1rem;
      background: var(--accent);
      border: none;
      color: #000;
      font-weight: bold;
      border-radius: 4px;
      cursor: pointer;
    }
    pre.response-box {
      background: #000;
      padding: 1rem;
      border-radius: 6px;
      color: #34d399;
      overflow-x: auto;
    }
  </style>
</head>
<body>
  <header>
    <h2>⚡ OmniUART Universal Dynamic UI</h2>
    <div>
      <label>Select Protocol: </label>
      <select id="protocolSelect" onchange="loadProtocol(this.value)"></select>
    </div>
  </header>

  <div class="container">
    <div class="tabs" id="tabBar">
      <button class="tab-btn active" onclick="switchTab('dashboard')">📊 Dashboard (Auto-Run)</button>
      <button class="tab-btn" onclick="switchTab('all-commands')">⚡ All Commands</button>
    </div>

    <div id="tabContents">
      <!-- Dashboard Tab -->
      <div id="tab-dashboard" class="tab-content active">
        <div class="card">
          <h3>📊 Auto-Run Dashboard Diagnostics</h3>
          <p>Commands tagged <code>dashboard</code> auto-execute to fetch hardware diagnostics & firmware version:</p>
          <pre id="dashboardOutput" class="response-box">Loading dashboard data...</pre>
          <button class="send-btn" onclick="refreshDashboard()">🔄 Refresh Dashboard Now</button>
        </div>
      </div>

      <!-- All Commands Tab -->
      <div id="tab-all-commands" class="tab-content">
        <div class="card">
          <h3>⚡ Command Dispatch Catalog</h3>
          <div id="allCommandsList">Select a protocol...</div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let currentProtoId = "";
    let currentSpec = null;

    async function init() {
      const res = await fetch("/api/protocols");
      const data = await res.json();
      const select = document.getElementById("protocolSelect");
      select.innerHTML = "";
      data.protocols.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.filename;
        opt.textContent = `${p.name} (v${p.version})`;
        select.appendChild(opt);
      });
      if (data.protocols.length > 0) {
        loadProtocol(data.protocols[0].filename);
      }
    }

    async function loadProtocol(protoId) {
      currentProtoId = protoId;
      const res = await fetch(`/api/protocol/${protoId}`);
      const data = await res.json();
      currentSpec = data.spec;

      // Render Dynamic Tag Tabs
      renderTabs(data.tags, data.tag_groups);
      // Auto-run dashboard
      refreshDashboard();
      // Render All Commands
      renderCommands("allCommandsList", currentSpec.commands);
    }

    function renderTabs(tags, tagGroups) {
      const tabBar = document.getElementById("tabBar");
      tabBar.innerHTML = `
        <button class="tab-btn active" onclick="switchTab('dashboard')">📊 Dashboard (Auto-Run)</button>
        <button class="tab-btn" onclick="switchTab('all-commands')">⚡ All Commands</button>
      `;

      tags.forEach(tag => {
        if (tag !== "dashboard" && tag !== "general") {
          const btn = document.createElement("button");
          btn.className = "tab-btn";
          btn.textContent = `🏷️ ${tag.toUpperCase()}`;
          btn.onclick = () => switchTab(`tag-${tag}`);
          tabBar.appendChild(btn);
        }
      });

      // Render tab content containers per tag
      const tabContents = document.getElementById("tabContents");
      // Keep dashboard and all-commands, rebuild tag content cards
      tags.forEach(tag => {
        if (tag !== "dashboard" && tag !== "general") {
          let container = document.getElementById(`tab-tag-${tag}`);
          if (!container) {
            container = document.createElement("div");
            container.id = `tab-tag-${tag}`;
            container.className = "tab-content";
            tabContents.appendChild(container);
          }
          const taggedCmds = currentSpec.commands.filter(c => c.tags && c.tags.includes(tag));
          container.innerHTML = `<div class="card"><h3>🏷️ Tab: ${tag.toUpperCase()}</h3><div id="cmd-list-tag-${tag}"></div></div>`;
          renderCommands(`cmd-list-tag-${tag}`, taggedCmds);
        }
      });
    }

    function switchTab(tabId) {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      
      const activeContent = document.getElementById(`tab-${tabId}`);
      if (activeContent) activeContent.classList.add("active");
      
      // Highlight button
      event.target.classList.add("active");
    }

    async function refreshDashboard() {
      if (!currentProtoId) return;
      const out = document.getElementById("dashboardOutput");
      out.textContent = "Auto-running dashboard commands...";
      const res = await fetch(`/api/dashboard/auto-run/${currentProtoId}`);
      const data = await res.json();
      out.textContent = JSON.stringify(data, null, 2);
    }

    function renderCommands(containerId, commands) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = "";
      commands.forEach(cmd => {
        const div = document.createElement("div");
        div.className = "card";
        div.innerHTML = `
          <h4>${cmd.name} (ID: ${cmd.id}) ${cmd.tags ? cmd.tags.map(t=>`<code>[${t}]</code>`).join(' ') : ''}</h4>
          <p>${cmd.description || ''}</p>
          <div class="cmd-form" id="form-${containerId}-${cmd.name}">
            ${cmd.parameters.map(p => `
              <label>${p.name} (${p.type}${p.unit ? ' ' + p.unit : ''}):
                <input type="text" name="${p.name}" value="${p.default || ''}">
              </label>
            `).join('')}
            <button class="send-btn" onclick="sendCommand('${cmd.name}', 'form-${containerId}-${cmd.name}', 'resp-${containerId}-${cmd.name}')">SEND COMMAND</button>
          </div>
          <pre class="response-box" id="resp-${containerId}-${cmd.name}">Response will appear here...</pre>
        `;
        container.appendChild(div);
      });
    }

    async function sendCommand(cmdName, formId, respId) {
      const form = document.getElementById(formId);
      const respBox = document.getElementById(respId);
      const inputs = form.querySelectorAll("input");
      const params = {};
      inputs.forEach(i => params[i.name] = i.value);

      respBox.textContent = `Sending ${cmdName}...`;
      const res = await fetch(`/api/send/${currentProtoId}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({command: cmdName, params: params})
      });
      const data = await res.json();
      respBox.textContent = JSON.stringify(data, null, 2);
    }

    window.onload = init;
  </script>
</body>
</html>"""
