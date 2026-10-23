# OmniUART CLI Reference & Usage Guide (#227)

OmniUART provides a command-line interface (`omniuart`) for protocol introspection, command dispatching, automated test script execution, fuzzing, traffic replay, artefact generation, and interactive UI workbench launching.

---

## 1. Catalogue Discovery & Introspection

### `omniuart list`
Discovers all available protocol definition schemas and test scripts in default catalogue directories (`schemas/`, `examples/protocols/`, `examples/scripts/`).

```bash
omniuart list
omniuart list --json
```

### `omniuart info <protocol>`
Displays detailed protocol documentation, configuration, frame parameters, opcodes, and tags.

```bash
omniuart info binary_sensor_node
omniuart info modbus-rtu
```

---

## 2. Command Dispatching (`send`)

Executes a single command against a physical serial port or virtual device simulator.

```bash
# Dispatch command against virtual simulator
omniuart send binary_sensor_node ping --virtual

# Dispatch command against physical serial port
omniuart send binary_sensor_node get_readings --port COM3 --baudrate 115200 --param channel=0

# Record session traffic to JSONL capture file
omniuart send binary_sensor_node get_readings --virtual --record capture.jsonl
```

---

## 3. Automated Test Script Execution (`run`)

Executes ordered test script steps with assertions and retries.

```bash
# Run automated test suite against virtual device
omniuart run sensor_test_suite.yaml --virtual

# Run test script with detailed JSON execution report
omniuart run sensor_test_suite.yaml --virtual --report report.json
```

---

## 4. Protocol Linting & Validation (`lint`)

Validates protocol definition YAML/JSON against OmniUART schema specifications.

```bash
omniuart lint examples/protocols/binary_sensor_node.yaml
```

---

## 5. Protocol Fuzzing (`fuzz`)

Runs fuzzing campaign with seedable random mutations, truncation, out-of-bounds, and byte insertion vectors.

```bash
# Run fuzz campaign with 50 test vectors and fixed seed
omniuart fuzz binary_sensor_node -n 50 --seed 42 --virtual
```

---

## 6. Traffic Replay (`replay`)

Replays recorded traffic sessions against target serial interfaces with timing control.

```bash
# Replay recorded session at 2x speed against virtual transport
omniuart replay capture.jsonl --speed 2.0 --virtual
```

---

## 7. Artefact Generation (`generate`)

Generates Wireshark Lua dissectors, C header files, Python dataclasses, JSON schemas, or AsyncAPI specs from protocol definitions.

```bash
# Generate C header file
omniuart generate c binary_sensor_node

# Generate Python dataclasses
omniuart generate python binary_sensor_node

# Generate Wireshark Lua dissector
omniuart generate wireshark binary_sensor_node

# Export AsyncAPI 2.6.0 specification
omniuart generate asyncapi binary_sensor_node

# Export JSON Schema
omniuart generate schema
```

---

## 8. Interactive Workbench (`ui`)

Launches local control workbench in Web browser or native Desktop mode.

```bash
# Launch Web Control Workbench
omniuart ui --mode web --port 8000

# Launch Native Desktop GUI Workbench
omniuart ui --mode desktop
```

## 9. Device Console (`dashboard`)

Opens the live device console for one protocol in the web workbench. It uses the protocol's saved Device UI definition (from `.omniuart/ui/` or the bundled `examples/device_ui/`), or one inferred from the protocol.

```bash
# Open the device console for the binary sensor node
omniuart dashboard binary_sensor_node
```

Connect a port, or the simulated device, from the workbench first. In the console:

- Command buttons and parameter controls send real commands. A command marked `mutating` or `destructive`, or one with a safety rule, asks for confirmation first.
- Values come only from the device's responses, and are shown as current, stale or offline. *Read device* sends every read-only command that needs no input; *Auto refresh* repeats it every two seconds.
- The Engineer view lists each exchange with its frames, latency and CRC result. The Developer view shows the raw frame log, the connection and the stored state.
- A transfer widget uploads a file through the commands named in the UI definition's `transfer_protocol`. The file counts as installed only when the device accepts the commit command.

The console uses `GET /api/device/{protocol}/state`, `POST /api/device/{protocol}/refresh` and `POST /api/device/{protocol}/transfer`, with `GET` and `POST .../transfer/{job}/cancel` for a running transfer.
