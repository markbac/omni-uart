# About OmniUART: Universal Schema-Driven UART Protocol Workbench

<p align="center">
  <img src="https://img.shields.io/badge/Release-v1.9.0-blue.svg" alt="Release">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-orange.svg" alt="Platforms">
  <img src="https://img.shields.io/badge/AsyncAPI-2.6.0-emerald.svg" alt="AsyncAPI 2.6.0">
</p>

> **OmniUART is a universal, schema-driven hardware protocol workbench and telemetry visualization tool for embedded systems, IoT devices, and hardware test engineering.**

---

## 💡 About OmniUART

Embedded software developers, test engineers, and hardware integrators frequently waste valuable time writing custom, ad-hoc Python or C scripts to send commands, parse packet responses, verify CRCs, and log serial communications for every new microcontroller or IoT peripheral.

**OmniUART solves this problem by completely decoupling hardware protocol logic from tooling.** By capturing framing parameters, packet envelopes, byte-slicing rules, parametric CRCs, and command signatures in **declarative JSON or YAML specifications**, OmniUART automatically provides:

- 💻 **Interactive Web & Native Desktop UI**: Multi-tab serial terminal, dynamic parameter forms, 60 FPS streaming spectrum telemetry plotter, and signal quality charts.
- ⚡ **Ad-hoc CLI Command Runner**: Send commands, format parameters, and parse structured serial responses directly from your terminal.
- 📜 **Automated Sequence Test Runner**: Execute multi-step test scripts with expected field assertions, timeouts, repeat loops, and automated PASS/FAIL reporting.
- 🧪 **Boundary Mutation Fuzzer**: Inject field boundary mutations, length mismatches, bitflips, and invalid CRCs to test device firmware resilience.
- ⏺️ **Wireshark PCAPNG Session Recording & Replay**: Capture microsecond-timestamped transactions and export directly to `.pcapng`, `.jsonl`, or raw `.bin`, with real-time replay onto target hardware.
- 📡 **Telemetry Bridge**: Stream parsed sensor data directly to **MQTT brokers** (`omniuart/telemetry/<cmd>`) and **HTTP Webhooks**.
- 📄 **AsyncAPI 2.6.0 Documentation Generator**: Auto-generate formal AsyncAPI specifications and interactive HTML documentation for any hardware protocol.

OmniUART is distributed as a **zero-dependency standalone executable** for Windows and Linux—no Python or Node environment required.

---

## 📚 MkDocs System Documentation Hub

Explore the complete collection of user guides, architectural specifications, JSON schemas, and test strategies:

| Documentation Hub Page | Direct Link | Purpose & Contents |
| :--- | :--- | :--- |
| 📖 **User Manual & CLI Guide** | [Read User Manual](release/guidance.md) | Installation, standalone executable usage, CLI subcommands (`send`, `run`, `fuzz`, `replay`), Desktop & Web UI, and logging. |
| 🏛️ **System Architecture** | [Explore Architecture](architecture/system-architecture.md) | C4 architectural diagrams, framing pipeline, transport abstraction, virtual device simulation, and state machines. |
| ⚙️ **Protocol Specification** | [View Protocol Spec](specs/protocol-schema-specification.md) | Specification for YAML/JSON protocol envelopes, framing modes, parametric CRCs (Rocksoft model), and payload fields. |
| 📜 **Automation Script Spec** | [View Script Spec](specs/script-schema-specification.md) | Sequence runner step schemas, parameter injection, response assertions, delay timers, and loop execution. |
| ⚙️ **Declarative JSON Schemas** | [Inspect JSON Schemas](schemas/index.md) | Official JSON Schema files for IDE auto-completion, linting, and automated protocol schema validation. |
| 🧪 **Test Strategy & Quality** | [View Test Strategy](testing/test-strategy.md) | Automated unit testing, standalone binary smoke testing, loopback transport tests, and CI/CD verification pipelines. |

---

## 🔌 Hardware Protocols & AsyncAPI Tooling Specifications

OmniUART features built-in integration with `@asyncapi/cli` and `@asyncapi/html-template` (via `npx asyncapi`) to convert declarative UART protocol definitions into standard **AsyncAPI 2.6.0** hardware interface specifications.

- 📚 **[Browse Full Hardware Protocol Catalog](protocols/index.md)**: Explore 32+ pre-configured hardware protocols, including AT Commands, Modbus RTU/ASCII, COBS, SLIP, BACnet MS/TP, MAVLink, DMX512, UBX, XBee, and custom CRC node protocols.
- 📄 **AsyncAPI Artifacts**: Download standalone AsyncAPI 2.6.0 `.yaml` files or view interactive single-file AsyncAPI HTML specifications for any protocol.

---

## 💾 Download Executable Releases

| Platform | Download Link | Quickstart Command |
| :--- | :--- | :--- |
| **Windows (64-bit)** | [📦 Download `omni-uart-windows-amd64.zip`](https://github.com/markbac/omni-uart/releases/latest/download/omni-uart-windows-amd64.zip) | Double-click `omni-uart-windows-amd64.exe` to open Desktop App |
| **Linux (64-bit)** | [📦 Download `omni-uart-linux-amd64.tar.gz`](https://github.com/markbac/omni-uart/releases/latest/download/omni-uart-linux-amd64.tar.gz) | `tar -xzf omni-uart-linux-amd64.tar.gz && ./omni-uart-linux-amd64` |

---

## 📖 Protocol Definition Example

Declarative YAML protocol specification (`BinarySensorNode.yaml`):

```yaml
schema_version: "1.0.0"
metadata:
  name: "BinarySensorNode"
  version: "1.1.0"
  description: "Binary UART protocol for multi-channel environmental sensor node with CRC16-Modbus"

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
  footer: [0x55, 0xAA]

commands:
  - name: "get_readings"
    id: 0x02
    description: "Query sensor channel temperature and humidity readings"
    parameters:
      - name: "channel"
        type: "uint8"
        min: 0
        max: 3
    response:
      id: 0x82
      fields:
        - name: "temperature"
          type: "float32"
          unit: "°C"
        - name: "humidity"
          type: "float32"
          unit: "%"
```
