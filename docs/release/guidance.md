# OmniUART Release Guidance & Complete User Manual

## 1. Quickstart Guide (No Python Required)

OmniUART is distributed as a standalone, single-file binary for **Windows** and **Linux**. You do **not** need Python installed.

### 1.1 Download Links & Installation

#### Windows
1. Download `omni-uart-windows-amd64.zip` from the latest GitHub Release.
2. Extract the zip archive.
3. Double-click `omni-uart-windows-amd64.exe` to launch the **Interactive Web UI** immediately in your default browser, or run via PowerShell:
   ```powershell
   .\omni-uart-windows-amd64.exe --help
   ```

#### Linux
1. Download `omni-uart-linux-amd64.tar.gz` from the latest GitHub Release.
2. Extract and make executable:
   ```bash
   tar -xzf omni-uart-linux-amd64.tar.gz
   chmod +x omni-uart-linux-amd64
   ./omni-uart-linux-amd64 --help
   ```

---

## 2. Execution Modes & CLI Reference

### 2.1 Interactive GUI Mode (Default Double-Click)
Running the executable with no CLI parameters automatically starts the local Web UI server and opens your browser:
```bash
# Starts Web UI on http://127.0.0.1:8000 and opens browser
omni-uart
```
Or specify custom host/port:
```bash
omni-uart ui --host 127.0.0.1 --port 8080
```

### 2.2 CLI Commands

#### 1. `list`: Auto-Discover Catalog Protocols & Scripts
```bash
omni-uart list
```
Displays all 32+ discovered protocol definition files and test scripts. Use `--json` for structured JSON output.

#### 2. `info`: Protocol Help & Tagged Command Catalog
```bash
omni-uart info binary_sensor_node.yaml
omni-uart info ubx-uart-interface.json
```
Displays baud rate, bytesize, framing rules, CRC integrity algorithm, parameters, response fields, and tag categories (`[DASHBOARD TAB]`, `[GENERAL TAB]`).

#### 3. `send`: Format & Dispatch Command
```bash
# Transmit on a real serial port and decode the response
omni-uart send binary_sensor_node get_readings --params channel=1 --port /dev/ttyUSB0

# Transmit to the built-in simulated device (no hardware needed)
omni-uart send binary_sensor_node get_readings --params channel=1 --virtual

# Only build and print the frame; nothing is transmitted
omni-uart send binary_sensor_node get_readings --params channel=1 --dry-run
```
Encodes the command with the protocol's framing and CRC, transmits it, waits for the response (the command's `response.timeout_ms`, or `--timeout`), and prints the decoded fields. Choose a transport with `--port` (any PySerial port name or URL, with `--baudrate` to override the protocol default) or `--virtual`; with neither and without `--dry-run`, the command refuses to run.

| Exit status | Meaning |
| :--- | :--- |
| `0` | Frame sent and, when the command defines a response, a valid response was decoded (or `--dry-run`). |
| `1` | No response before the timeout, or the response was invalid (bad CRC, wrong command, malformed). |
| `2` | Invalid input: unknown parameter, missing or out-of-range value, or no transport selected. |
| `3` | The serial port could not be opened or failed while transmitting. |

#### 4. `run`: Execute Automated Test Sequence Script
```bash
omni-uart run sensor_test_suite.yaml --port /dev/ttyUSB0
omni-uart run sensor_test_suite.yaml --virtual --record session.jsonl --report result.json
omni-uart run ubx-baud-switch-sequence.json --protocol ubx-uart-interface.json --port COM3
```
Executes the script's steps in order against a real serial port (`--port`) or the built-in simulated device (`--virtual`): sends commands, waits for responses with timeouts, evaluates field assertions, applies delays and variables, and stops at the first failure unless the script sets `abort_on_error: false`. The protocol is taken from the script's `meta.protocol` (a catalog name or file path) unless `--protocol` is given. `--record` writes every frame to a `.jsonl` session file and `--report` writes a JSON result.

Exit status: `0` all steps passed, `1` a step failed, `2` invalid script or input, `3` transport error. See the [Script Specification](../specs/script-schema-specification.md).

#### 5. `fuzz`: Boundary Mutation Campaign Engine
```bash
omni-uart fuzz binary_sensor_node.yaml --vectors 50 --seed 42
```
`--seed` makes the random mutations reproducible. When `--vectors` is smaller than the full set, vectors are taken round-robin so every command is covered.

Runs a 50-vector mutation campaign built from the protocol (a valid baseline, an out-of-bounds parameter, a corrupted integrity field, a truncated frame and a random byte mutation per command; strategies that do not apply to a command are skipped). Every vector is classified from what the device did:

| Outcome | Meaning |
| :--- | :--- |
| `ACCEPTED` | A valid request was answered with a valid response. |
| `CORRECTLY_REJECTED` | An invalid request was ignored and the device still answered a valid probe afterwards. |
| `UNEXPECTEDLY_ACCEPTED` | An invalid request was answered as if it were valid. |
| `MALFORMED_RESPONSE` | The device sent bytes that do not decode as a valid response. |
| `TIMEOUT` | A valid request received no response. |
| `HANG` | The device stopped answering valid requests after this vector. |
| `TRANSPORT_ERROR` | The transport failed while writing or reading. |

The protocol schema defines no error frames, so staying silent is how a device rejects an invalid request. The command exits with status 0 only when every vector was handled correctly (`ACCEPTED` or `CORRECTLY_REJECTED`), and 1 otherwise.

#### 6. `replay`: Session Replay Engine
```bash
omni-uart replay session_log.jsonl --speed 2.0
```
Replays previously recorded `.jsonl` serial transactions back onto physical hardware or virtual loopback transports at 2.0x playback speed.

#### 7. `lint` & `convert`: Protocol Linter & Converter
```bash
omni-uart lint my_custom_protocol.yaml
omni-uart convert my_legacy_protocol.yaml -o schemas/my_protocol_kit.json
```

#### 8. `docs`: Build Static HTML/Markdown Documentation
```bash
omni-uart docs --all --output-dir _site
```

#### 9. `--log-file` and `--log-level`: Persistent File Logging
```bash
omni-uart --log-file ~/.omniuart/logs/session.log --log-level DEBUG list
```

---

## 3a. Native Desktop App Behaviour

The desktop app drives the same session, codec and script runner as the CLI and web API.

1. **Connect / Disconnect**: Choose a detected serial port, or `virtual` for the labelled simulated device, and press Connect. The button and status change only once the port has really opened; a missing or busy port shows the error and stays disconnected. Disconnect closes the port.
2. **Sending**: Commands from the Command Catalog are encoded by the protocol codec, written to the open link and answered with a decoded response. The Comms Streamer logs the bytes actually sent (TX), the bytes received (RX) with decoded fields, and any timeout or invalid response (ERR). Sending while disconnected transmits nothing.
3. **Script Runner**: Runs the selected script with the shared runner and shows the real PASSED, FAILED, ERROR or SKIPPED result per step, with each assertion's expected and actual value, and an overall result.
4. **Telemetry Plotter**: Plots only numeric fields decoded from valid RX frames (the first two numeric fields become Ch1 and Ch2). Transmitted bytes are never plotted and the axis shows real values. Text responses such as AT replies are shown in the Comms Streamer but not plotted.
5. **Auto-Poll**: Only commands tagged `dashboard` that expect a response and whose parameters all have defaults can be polled. Polling stops if the link is lost, and a new poll is not sent while the previous one is still waiting.
6. **Raw Send**: Hex or ASCII typed in the Comms Streamer is written unmodified and any reply is logged. The built-in AT and Modbus macro buttons were removed because they sent fixed bytes to whatever device was connected.

---

## 3. Dynamic Web UI Features

1. **Protocol Dropdown Selector**: Switch between any discovered hardware protocol interactively.
2. **Tag-Based Dynamic Tabs**: Generates tabs based on tags in protocol definitions.
3. **Auto-Run Dashboard Tab**: Automatically executes `dashboard`-tagged diagnostic commands on protocol switch to query hardware firmware version and uptime.
4. **60 FPS Real-Time WebSocket Comms Monitor**: Side-by-side visualization of raw hex frames and decoded key-value semantic byte trees.
5. **Theme Toggle & High-Density Compact Mode**:
   - `🌓 Theme`: Toggle between Dark, Light, and High-Contrast terminal modes.
   - `↕️ Compact`: Toggle high-density view for analyzing high-frequency 100 Hz+ packet streams.
6. **Session Exporters**: Export live serial captures directly to **Wireshark PCAPNG (`.pcapng`)**, **JSON Lines (`.jsonl`)**, **CSV (`.csv`)**, or **Raw Binary (`.bin`)**.
