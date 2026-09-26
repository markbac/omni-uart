# OmniUART: Universal Schema-Driven UART Protocol Tool

<p align="center">
  <img src="https://img.shields.io/badge/Release-v0.4.0-blue.svg" alt="Release">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-orange.svg" alt="Platforms">
</p>

> **Universal, schema-driven UART protocol tool for embedded systems, IoT devices, and hardware test engineering.**

OmniUART decouples protocol definitions from custom tooling code by using declarative JSON or YAML specifications. It provides an ad-hoc CLI, an automated test runner with assertions, a boundary mutation fuzzer, a session replayer, and an auto-generated dynamic Web UI with real-time 60 FPS WebSocket packet streaming.

Distributed as a **self-contained standalone executable** for Windows and Linux—no Python installation required.

---

## 💾 Download Executable Releases

| Platform | Download Link | Quickstart Command |
| :--- | :--- | :--- |
| **Windows (64-bit)** | [📦 Download `omni-uart-windows-amd64.zip`](https://github.com/markbac/omni-uart/releases/latest/download/omni-uart-windows-amd64.zip) | Double-click `omni-uart-windows-amd64.exe` to launch Web UI immediately |
| **Linux (64-bit)** | [📦 Download `omni-uart-linux-amd64.tar.gz`](https://github.com/markbac/omni-uart/releases/latest/download/omni-uart-linux-amd64.tar.gz) | `tar -xzf omni-uart-linux-amd64.tar.gz && ./omni-uart-linux-amd64` |

---

## ⚡ Key Features

- **Schema-Driven Protocols (JSON/YAML)**: Define message envelopes, sync preambles, dynamic length fields, opcodes, typed payload fields (integers, floats, enums, strings, bitfields), and footers.
- **Parametric CRC & Presets**: Pure-Python zero-dependency integrity engine supporting standard presets (CRC8, CRC16-Modbus, CRC16-CCITT, CRC32, Sum, XOR) and **fully custom parametric CRCs** via the Rocksoft Model (`width`, `poly`, `init`, `refin`, `refout`, `xorout`, `endian`).
- **Interactive Double-Click GUI Mode**: Double-clicking the standalone binary starts the Web UI server and opens your browser to `http://localhost:8000`.
- **Dual-View Raw & Decoded Stream Inspector**: Real-time side-by-side visualization with color-coded semantic byte slicing (Header, Length, Command, Payload, CRC, Footer) and interactive cross-highlighting.
- **Session Recording & Wireshark Export**: Record full serial transactions with microsecond timestamps and export to **Wireshark PCAPNG (`.pcapng`)**, JSON Lines (`.jsonl`), CSV, or raw binary (`.bin`).
- **Session Replay Engine**: Replay recorded `.jsonl` serial transactions back onto physical hardware or virtual loopback transports at real-time or scaled speed multipliers (`omni-uart replay`).
- **Telemetry Bridge**: Dispatches parsed UART telemetry events directly to **MQTT brokers** (`omniuart/telemetry/<cmd>`) and **HTTP Webhooks**.
- **DTR/RTS Bootloader Pin Pulsing**: Configurable hardware line toggling (DTR/RTS) for resetting ESP32/STM32 MCUs into bootloader mode prior to command execution.
- **Virtual MCU Simulation**: Test protocols and execute regression suites completely offline without physical hardware attached.

---

## 📖 Quick Start Example

```yaml
schema_version: "1.0.0"
metadata:
  name: "BinarySensorNode"
  version: "1.1.0"

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

---

## 🏛️ Documentation Sections

- [User Manual & Quickstart Guide](release/guidance.md): Detailed CLI subcommands, Web UI usage, themes, and session recording.
- [System Architecture](architecture/system-architecture.md): High-level system blocks, C4 diagrams, state machines, and subsystem contracts.
- [Protocol Schema Specification](specs/protocol-schema-specification.md): Formal YAML/JSON protocol definition schema specification.
- [Automation Script Specification](specs/script-schema-specification.md): Automation test script schema specification.
- [Hardware Protocols & AsyncAPI Catalog](protocols/index.md): Catalog of 32+ hardware protocols with auto-generated AsyncAPI 2.6.0 specifications.
