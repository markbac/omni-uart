"""Single-Page Application HTML/CSS/JS Template View Provider for OmniUART Web UI."""

from __future__ import annotations


def get_index_html() -> str:
    """Return the single-page HTML/CSS/JS application template."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OmniUART Dynamic Tag-Based Web UI Workspace</title>
  <style>
    :root {
      --bg-color: #0f172a;
      --card-bg: #1e293b;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --text: #f8fafc;
      --border: #334155;
      --success: #16a34a;
    }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg-color);
      color: var(--text);
    }
    header {
      padding: 0.75rem 1.5rem;
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }
    .connection-bar {
      display: flex;
      gap: 0.5rem;
      align-items: center;
      background: #0f172a;
      padding: 4px 12px;
      border-radius: 6px;
      border: 1px solid var(--border);
    }
    .workspace-nav {
      display: flex;
      gap: 0.25rem;
      background: #0f172a;
      padding: 0.5rem 1.5rem;
      border-bottom: 1px solid var(--border);
    }
    .nav-tab {
      padding: 0.5rem 1rem;
      border-radius: 6px;
      background: transparent;
      color: var(--text);
      border: 1px solid transparent;
      cursor: pointer;
      font-weight: 600;
    }
    .nav-tab.active {
      background: var(--card-bg);
      color: var(--accent);
      border-color: var(--border);
    }
    .workspace-panel {
      display: none;
      padding: 1.5rem;
    }
    .workspace-panel.active {
      display: block;
    }
    .layout-grid {
      display: grid;
      grid-template-columns: 280px 1fr;
      gap: 1.5rem;
    }
    .cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1rem;
    }
    .card {
      background: var(--card-bg);
      padding: 1.25rem;
      border-radius: 8px;
      border: 1px solid var(--border);
    }
    .card-accordion-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
    }
    .cmd-form {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      margin-top: 1rem;
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
    button.send-btn:hover {
      background: var(--accent-hover);
    }
    pre.response-box {
      background: #000;
      padding: 0.75rem;
      border-radius: 6px;
      color: #34d399;
      overflow-x: auto;
      max-height: 400px;
    }
    body.light-theme {
      --bg-color: #f8fafc;
      --card-bg: #ffffff;
      --text: #0f172a;
      --border: #cbd5e1;
    }
    body.compact-mode .card {
      padding: 0.5rem;
      margin-bottom: 0.5rem;
    }
    body.compact-mode pre.response-box {
      max-height: 250px;
      font-size: 0.85rem;
    }
    .badge-tx { background: #0284c7; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
    .badge-rx { background: #16a34a; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
    .badge-disc { background: #d97706; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-family: monospace; font-size: 0.85rem; }
    .tree-item { cursor: pointer; padding: 4px 8px; border-radius: 4px; user-select: none; }
    .tree-item:hover { background: #334155; color: #38bdf8; }
    .tree-node { margin-left: 12px; border-left: 1px dashed var(--border); padding-left: 8px; }
  </style>
</head>
<body>
  <header>
    <div style="display: flex; align-items: center; gap: 1rem;">
      <h2 style="margin: 0;">⚡ OmniUART Control Workbench</h2>
      <button onclick="document.body.classList.toggle('light-theme')" style="background:var(--card-bg); border:1px solid var(--border); color:var(--text); padding:5px 10px; border-radius:4px; cursor:pointer;">🌓 Theme</button>
      <button onclick="document.body.classList.toggle('compact-mode')" style="background:var(--card-bg); border:1px solid var(--border); color:var(--text); padding:5px 10px; border-radius:4px; cursor:pointer;">↕️ Compact</button>
      <label>Protocol: </label>
      <select id="protocolSelect" onchange="loadProtocol(this.value)"></select>
    </div>

    <!-- Serial Port Connection Toolbar -->
    <div class="connection-bar">
      <span>🔌 Serial Port:</span>
      <select id="portSelect"></select>
      <select id="baudSelect">
        <option value="9600">9600 bps</option>
        <option value="115200" selected>115200 bps</option>
        <option value="230400">230400 bps</option>
        <option value="921600">921600 bps</option>
      </select>
      <button id="connectBtn" class="send-btn" onclick="toggleSerialConnect()">CONNECT</button>
    </div>
  </header>

  <!-- Top Workspace Navigation -->
  <div class="workspace-nav">
    <button class="nav-tab active" onclick="switchWorkspace('dashboard')">📊 Dashboard</button>
    <button class="nav-tab" onclick="switchWorkspace('catalog')">⚡ Command Catalog</button>
    <button class="nav-tab" onclick="switchWorkspace('telemetry')">📈 Telemetry Plotter</button>
    <button class="nav-tab" onclick="switchWorkspace('scripts')">📜 Script Runner</button>
    <button class="nav-tab" onclick="switchWorkspace('comms')">📡 Comms Streamer</button>
  </div>

  <!-- Workspace Panels -->
  <main>
    <!-- Panel 1: Dashboard -->
    <div id="panel-dashboard" class="workspace-panel active">
      <div class="card">
        <h3>📊 Auto-Run Diagnostics Dashboard</h3>
        <p>Commands tagged <code>dashboard</code> automatically run on protocol selection to fetch version and status:</p>
        <pre id="dashboardOutput" class="response-box">Loading dashboard diagnostics...</pre>
        <button class="send-btn" onclick="refreshDashboard()">🔄 Refresh Dashboard</button>
      </div>
    </div>

    <!-- Panel 2: Command Catalog -->
    <div id="panel-catalog" class="workspace-panel">
      <div class="layout-grid">
        <!-- Side Tree Tag Navigator -->
        <div>
          <div class="card">
            <h3 style="margin-top:0;">🌳 Protocol Tag Tree</h3>
            <div id="tagTreeMenu">Loading command tree...</div>
          </div>
        </div>

        <!-- Responsive Card Grid -->
        <div>
          <div class="card" style="margin-bottom: 1rem;">
            <h3 style="margin: 0;">⚡ Command Dispatch Grid</h3>
          </div>
          <div id="allCommandsGrid" class="cards-grid">Select a protocol...</div>
        </div>
      </div>
    </div>

    <!-- Panel 3: Live Telemetry Line Plotter -->
    <div id="panel-telemetry" class="workspace-panel">
      <div class="card">
        <h3>📈 Live Real-Time Telemetry Line Plotter</h3>
        <p>Real-time line charts plotting numeric parameter streams over time:</p>
        <div style="display:flex; gap: 1rem; align-items: center; margin-bottom: 1rem;">
          <label>Field Stream: </label>
          <select id="telemetryFieldSelect">
            <option value="temperature">temperature (°C)</option>
            <option value="voltage">voltage (V)</option>
            <option value="channel_reading">channel_reading (raw)</option>
          </select>
          <button class="send-btn" onclick="clearTelemetryPlot()">Clear Plot</button>
        </div>
        <canvas id="telemetryCanvas" width="900" height="350" style="background:#000; border-radius:6px; width:100%; border:1px solid var(--border);"></canvas>
      </div>
    </div>

    <!-- Panel 4: Interactive Script Runner -->
    <div id="panel-scripts" class="workspace-panel">
      <div class="card">
        <h3>📜 Interactive Automation Script Runner</h3>
        <p>Select declarative test sequence script (<code>script.schema.json</code>) to run automated regression suite:</p>
        <div style="display:flex; gap: 1rem; align-items: center; margin-bottom: 1rem;">
          <label>Select Script: </label>
          <select id="scriptSelect"></select>
          <button class="send-btn" onclick="runSelectedScript()">🚀 Run Automated Sequence</button>
        </div>
        <pre id="scriptOutput" class="response-box">Select script and click Run Automated Sequence...</pre>
      </div>
    </div>

    <!-- Panel 5: Comms Panel Streamer -->
    <div id="panel-comms" class="workspace-panel">
      <div class="card">
        <h3>📡 Real-Time Comms Traffic Monitor (WebSocket 60 FPS)</h3>
        <p>Live TX/RX packet events, hexadecimal dumps, and decoded trees:</p>
        <div style="margin-bottom: 0.5rem;">
          <button onclick="clearCommsLog()" style="background:#ef4444; color:#fff; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;">Clear Log</button>
          <span id="wsStatus" style="margin-left:10px; color:#38bdf8;">Connecting...</span>
        </div>
        <pre id="commsLog" class="response-box" style="height: 500px;">Waiting for serial traffic...</pre>
      </div>
    </div>
  </main>

  <script>
    let currentProtoId = "";
    let currentSpec = null;
    let ws = null;
    let isConnected = false;
    let plotData = [];

    function connectWebSocket() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/serial`;
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        document.getElementById("wsStatus").textContent = "🟢 Live Connected (60 FPS Stream)";
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.event === "connected") return;
        appendCommsEvent(data);
        if (data.decoded_fields) {
          updateTelemetryPlot(data.decoded_fields);
        }
      };

      ws.onclose = () => {
        document.getElementById("wsStatus").textContent = "🔴 Disconnected - Retrying...";
        setTimeout(connectWebSocket, 2000);
      };
    }

    function appendCommsEvent(event) {
      const log = document.getElementById("commsLog");
      const badge = event.direction === "tx" ? `<span class="badge-tx">TX</span>` : `<span class="badge-rx">RX</span>`;
      const timeStr = new Date(event.timestamp * 1000).toISOString().split("T")[1].slice(0, 12);
      const line = `${timeStr} ${badge} [${event.command_name || 'raw'}] HEX: ${event.raw_hex} | DECODED: ${JSON.stringify(event.decoded_fields)}\\n`;
      log.textContent = line + log.textContent;
    }

    function clearCommsLog() {
      document.getElementById("commsLog").textContent = "";
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({action: "clear"}));
      }
    }

    function switchWorkspace(panelId) {
      document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".workspace-panel").forEach(p => p.classList.remove("active"));
      const targetPanel = document.getElementById(`panel-${panelId}`);
      if (targetPanel) targetPanel.classList.add("active");
      if (event && event.target) event.target.classList.add("active");
    }

    async function init() {
      connectWebSocket();
      await loadSerialPorts();
      await loadScriptList();

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

    async function loadSerialPorts() {
      const res = await fetch("/api/serial/ports");
      const data = await res.json();
      const select = document.getElementById("portSelect");
      select.innerHTML = "";
      data.ports.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p;
        opt.textContent = p;
        select.appendChild(opt);
      });
      const virtual = document.createElement("option");
      virtual.value = data.virtual_port;
      virtual.textContent = "virtual (SIMULATED device)";
      select.appendChild(virtual);
    }

    async function toggleSerialConnect() {
      const btn = document.getElementById("connectBtn");
      const port = document.getElementById("portSelect").value;
      const baud = parseInt(document.getElementById("baudSelect").value);
      const res = isConnected
        ? await fetch("/api/serial/disconnect", {method: "POST"})
        : await fetch("/api/serial/connect", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({port: port, baudrate: baud, rts: true, dtr: true, protocol: currentProtoId})
          });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(`Serial ${isConnected ? "disconnect" : "connect"} failed: ${JSON.stringify(err.detail || err)}`);
        return;
      }
      const data = await res.json();
      isConnected = data.connection.connected;
      btn.textContent = isConnected ? "DISCONNECT" : "CONNECT";
      btn.style.background = isConnected ? "#ef4444" : "var(--accent)";
    }

    async function loadScriptList() {
      const res = await fetch("/api/scripts");
      const data = await res.json();
      const select = document.getElementById("scriptSelect");
      select.innerHTML = "";
      data.scripts.forEach(s => {
        const opt = document.createElement("option");
        opt.value = s.name;
        opt.textContent = s.filename;
        select.appendChild(opt);
      });
    }

    async function runSelectedScript() {
      const scriptName = document.getElementById("scriptSelect").value;
      const out = document.getElementById("scriptOutput");
      out.textContent = `Executing automated sequence script '${scriptName}'...`;
      const res = await fetch(`/api/script/run/${scriptName}`, {method: "POST"});
      const data = await res.json();
      out.textContent = JSON.stringify(data, null, 2);
    }

    async function loadProtocol(protoId) {
      currentProtoId = protoId;
      const res = await fetch(`/api/protocol/${protoId}`);
      const data = await res.json();
      currentSpec = data.spec;

      renderTagTree(currentSpec.commands);
      refreshDashboard();
      renderCommands("allCommandsGrid", currentSpec.commands);
    }

    function renderTagTree(commands) {
      const treeContainer = document.getElementById("tagTreeMenu");
      if (!treeContainer) return;

      const tree = {};
      commands.forEach(cmd => {
        const tags = (cmd.tags && cmd.tags.length > 0) ? cmd.tags : ["general"];
        tags.forEach(t => {
          const parts = t.split("/");
          let curr = tree;
          parts.forEach((p, idx) => {
            if (!curr[p]) curr[p] = { _cmds: [] };
            if (idx === parts.length - 1) {
              curr[p]._cmds.push(cmd);
            }
            curr = curr[p];
          });
        });
      });

      function buildHtml(node, prefix = "") {
        let html = "";
        for (const k in node) {
          if (k === "_cmds") continue;
          const fullPath = prefix ? `${prefix}/${k}` : k;
          const cmdCount = node[k]._cmds.length;
          html += `
            <div class="tree-node">
              <span class="tree-item" onclick="filterByTagPath('${fullPath}')">📁 <strong>${k}</strong> (${cmdCount})</span>
              ${buildHtml(node[k], fullPath)}
            </div>
          `;
        }
        return html;
      }

      treeContainer.innerHTML = buildHtml(tree) || "<div>No tag hierarchy detected</div>";
    }

    function filterByTagPath(tagPath) {
      switchWorkspace('catalog');
      const filtered = currentSpec.commands.filter(c => c.tags && c.tags.some(t => t.startsWith(tagPath)));
      renderCommands("allCommandsGrid", filtered);
    }

    async function refreshDashboard() {
      if (!currentProtoId) return;
      const out = document.getElementById("dashboardOutput");
      out.textContent = "Auto-running dashboard commands...";
      const res = await fetch(`/api/dashboard/auto-run/${currentProtoId}`);
      const data = await res.json();
      out.textContent = JSON.stringify(data, null, 2);
    }

    function getDiscriminatorBadge(cmd) {
      let badge = "";
      if (cmd.parameters) {
        const disc = cmd.parameters.find(p => p.role === "discriminator" || p.constValue !== undefined);
        if (disc) {
          const val = disc.constValue !== undefined ? disc.constValue : disc.default;
          badge = `<span class="badge-disc">Opcode: ${disc.name}=${val}</span>`;
        }
      }
      if (!badge && cmd.id !== undefined) {
        const cmdIdStr = typeof cmd.id === 'number' ? `0x${cmd.id.toString(16).toUpperCase().padStart(2, '0')}` : cmd.id;
        badge = `<span class="badge-disc">ID: ${cmdIdStr}</span>`;
      }
      return badge;
    }

    function renderCommands(containerId, commands) {
      const container = document.getElementById(containerId);
      if (!container) return;
      container.innerHTML = "";
      commands.forEach(cmd => {
        const div = document.createElement("div");
        div.className = "card";
        const discBadge = getDiscriminatorBadge(cmd);
        div.innerHTML = `
          <div class="card-accordion-header">
            <h4 style="margin:0;">${cmd.name} ${discBadge}</h4>
            <span>▼</span>
          </div>
          <p style="font-size:0.9rem; color:#94a3b8;">${cmd.description || ''}</p>
          <div class="cmd-form" id="form-${containerId}-${cmd.name}">
            ${cmd.parameters.map(p => renderFormField(p)).join('')}
            <button class="send-btn" onclick="sendCommand('${cmd.name}', 'form-${containerId}-${cmd.name}', 'resp-${containerId}-${cmd.name}')">SEND COMMAND</button>
          </div>
          <pre class="response-box" id="resp-${containerId}-${cmd.name}">Response payload...</pre>
        `;
        container.appendChild(div);
      });
    }

    function renderFormField(p) {
      if (p.options) {
        const optsHtml = Object.entries(p.options).map(([k, v]) => `<option value="${k}">${k}: ${v}</option>`).join('');
        return `<label>${p.name} (${p.type}): <select name="${p.name}">${optsHtml}</select></label>`;
      } else if (p.type === 'bool') {
        return `<label style="display:flex; align-items:center; gap:8px;">${p.name}: <input type="checkbox" name="${p.name}" ${p.default ? 'checked' : ''}></label>`;
      } else if (p.min !== null && p.max !== null && p.min !== undefined && p.max !== undefined) {
        return `<label>${p.name} [${p.min}..${p.max}] ${p.unit || ''}: <input type="range" name="${p.name}" min="${p.min}" max="${p.max}" value="${p.default || p.min}" oninput="this.nextElementSibling.value=this.value"> <output>${p.default || p.min}</output></label>`;
      } else {
        return `<label>${p.name} (${p.type}${p.unit ? ' ' + p.unit : ''}): <input type="text" name="${p.name}" value="${p.default !== null && p.default !== undefined ? p.default : ''}"></label>`;
      }
    }

    async function sendCommand(cmdName, formId, respId) {
      const form = document.getElementById(formId);
      const respBox = document.getElementById(respId);
      const inputs = form.querySelectorAll("input, select");
      const params = {};
      inputs.forEach(i => {
        if (i.type === 'checkbox') params[i.name] = i.checked;
        else params[i.name] = i.value;
      });

      respBox.textContent = `Sending ${cmdName}...`;
      const res = await fetch(`/api/send/${currentProtoId}`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({command: cmdName, params: params})
      });
      const data = await res.json();
      respBox.textContent = JSON.stringify(data, null, 2);
    }

    function updateTelemetryPlot(fields) {
      const selectedField = document.getElementById("telemetryFieldSelect").value;
      if (fields[selectedField] !== undefined) {
        plotData.push(fields[selectedField]);
        if (plotData.length > 50) plotData.shift();
        drawTelemetryCanvas();
      }
    }

    function clearTelemetryPlot() {
      plotData = [];
      drawTelemetryCanvas();
    }

    function drawTelemetryCanvas() {
      const canvas = document.getElementById("telemetryCanvas");
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (plotData.length < 2) return;

      const minVal = Math.min(...plotData);
      const maxVal = Math.max(...plotData);
      const range = (maxVal - minVal) || 1;

      ctx.beginPath();
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2;

      plotData.forEach((val, idx) => {
        const x = (idx / (plotData.length - 1)) * (canvas.width - 40) + 20;
        const y = canvas.height - 20 - ((val - minVal) / range) * (canvas.height - 40);
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }

    window.onload = init;
  </script>
</body>
</html>"""
