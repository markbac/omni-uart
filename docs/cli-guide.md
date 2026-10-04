# OmniUART CLI Reference & Usage Guide (#227)

OmniUART provides a command-line interface (`omniuart`) for protocol introspection, command dispatching, automated test script execution, fuzzing, traffic replay, artifact generation, and interactive UI workbench launching.

---

## 1. Catalog Discovery & Introspection

### `omniuart list`
Discovers all available protocol definition schemas and test scripts in default catalog directories (`schemas/`, `examples/protocols/`, `examples/scripts/`).

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

## 7. Artifact Generation (`generate`)

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
