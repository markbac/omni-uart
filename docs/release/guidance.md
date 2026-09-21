# OmniUART Release Guidance & User Manual

## 1. Quickstart Guide (No Python Required)

OmniUART is distributed as a standalone, single-file binary. You do **not** need Python installed.

### 1.1 Download and Run

#### Windows
1. Download `omni-uart-windows-amd64.exe` from the latest GitHub Release.
2. Open PowerShell or Command Prompt.
3. Verify installation:
   ```powershell
   .\omni-uart-windows-amd64.exe --version
   ```

#### Linux
1. Download `omni-uart-linux-amd64.tar.gz` from the latest GitHub Release.
2. Extract and make executable:
   ```bash
   tar -xzf omni-uart-linux-amd64.tar.gz
   chmod +x omni-uart
   ./omni-uart --version
   ```

#### macOS
1. Download `omni-uart-macos-universal.tar.gz`.
2. Extract and run:
   ```bash
   tar -xzf omni-uart-macos-universal.tar.gz
   chmod +x omni-uart
   ./omni-uart --version
   ```

---

## 2. Operational Modes

### Mode 1: Interactive CLI & Direct Commands
Send individual commands to a target hardware device or virtual simulator:

```bash
# List available hardware serial ports
omni-uart ports

# Send a command to a physical serial port
omni-uart send set_led --protocol protocols/sensor_node.yaml --port COM3 --baud 115200 --color red --brightness 80

# Send a command in offline Virtual Device mode
omni-uart send ping --protocol protocols/sensor_node.yaml --virtual

# Sniff and decode incoming frames live
omni-uart monitor --protocol protocols/sensor_node.yaml --port COM3
```

### Mode 2: Automated Script Runner
Run automated validation and regression test suites with assertions:

```bash
# Run a test script against physical device
omni-uart run scripts/sensor_test_suite.yaml --protocol protocols/sensor_node.yaml --port COM3

# Run a test script in CI using Virtual MCU loopback (no hardware needed)
omni-uart run scripts/sensor_test_suite.yaml --protocol protocols/sensor_node.yaml --virtual --report-json report.json
```

### Mode 3: Dynamic Web Dashboard
Launch the schema-driven web UI:

```bash
# Launch dynamic web UI on default port (http://127.0.0.1:8080)
omni-uart ui --protocol protocols/sensor_node.yaml

# Launch on custom host/port
omni-uart ui --protocol protocols/sensor_node.yaml --host 0.0.0.0 --port 9000
```
The browser will automatically open, providing dynamic form controls, real-time packet inspectors, and live telemetry graphs.

---

## 3. Protocol Authoring Guide

Protocols are defined in YAML or JSON. A minimal binary protocol definition:

```yaml
schema_version: "1.0.0"
metadata:
  name: "SimpleSensor"
  version: "1.0.0"

serial_config:
  baudrate: 115200

framing:
  type: "binary"
  header: [0xAA, 0x55]
  length:
    type: "uint16"
    endian: "little"
    includes: "payload_only"
  command_id:
    type: "uint8"
  integrity:
    algorithm: "crc16_modbus"

commands:
  - name: "read_temperature"
    id: 0x01
    parameters: []
    response:
      id: 0x81
      timeout_ms: 1000
      fields:
        - name: "temp_celsius"
          type: "float32"
          endian: "little"
          unit: "°C"
```

Validate your protocol definition against the formal schema before use:
```bash
omni-uart validate protocols/my_protocol.yaml
```

---

## 4. Automation Script Authoring Guide

Automation scripts define ordered steps and assertions:

```yaml
version: "1.0.0"
meta:
  name: "Temperature Verification"
  protocol: "protocols/my_protocol.yaml"

config:
  abort_on_error: true
  default_timeout_ms: 1000

steps:
  - name: "Query Temperature"
    command: "read_temperature"
    expect_response: "read_temperature_response"
    assertions:
      - field: "temp_celsius"
        op: ">="
        value: 15.0
      - field: "temp_celsius"
        op: "<="
        value: 40.0
```
