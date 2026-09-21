# OmniUART: Universal Schema-Driven UART Protocol Tool

[![CI](https://github.com/markbac/omni-uart/actions/workflows/ci.yml/badge.svg)](https://github.com/markbac/omni-uart/actions/workflows/ci.yml)
[![Release](https://github.com/markbac/omni-uart/actions/workflows/release.yml/badge.svg)](https://github.com/markbac/omni-uart/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

> **Universal, schema-driven UART protocol tool for embedded systems, IoT devices, and hardware test engineering.**

OmniUART decouples protocol definitions from custom tooling code by using declarative JSON or YAML specifications. It provides an ad-hoc CLI, an automated test runner with assertions, and an auto-generated dynamic web UI with real-time streaming TX/RX packet inspection.

Distributed as a **self-contained standalone executable** for Windows, Linux, and macOS—no Python installation required.

---

## Key Features

- **Schema-Driven Protocols (JSON/YAML)**: Define message envelopes, sync preambles, dynamic length fields, opcodes, typed payloads (integers, floats, enums, strings, bitfields), and footers.
- **Custom Parametric CRC & Presets**: Pure-Python, zero-dependency integrity engine supporting standard presets (CRC8, CRC16-Modbus, CRC16-CCITT, CRC32, Sum, XOR) and **fully custom parametric CRCs** via the Rocksoft Model (`width`, `poly`, `init`, `refin`, `refout`, `xorout`, `endian`).
- **Dual-View Raw & Decoded Stream Inspector**: Real-time side-by-side visualization with color-coded semantic byte slicing (Header, Length, Command, Payload, CRC, Footer) and interactive cross-highlighting.
- **Session Recording & Export**: Record full serial transactions with microsecond timestamps and export to JSON Lines (`.jsonl`), CSV, or raw binary (`.bin`) for post-session analysis or automated playback.
- **Three Operational Modes**:
  1. **Interactive CLI**: Send commands, format parameters, and decode responses on the command line.
  2. **Batch Script Runner**: Execute automated test sequences with timeouts, delays, and assertions, producing JSON and JUnit XML reports.
  3. **Auto-Generated Web UI**: Zero-dependency local web interface (FastAPI + WebSockets) that dynamically builds forms for any loaded protocol, streams decoded frames, and provides session controls.
- **Virtual MCU Simulation**: Test protocols and execute regression suites completely offline without physical hardware attached.
- **Docs-as-Code & Zero-Defect Architecture**: Formal specifications, schemas, and comprehensive test suites for every subsystem.
- **Standalone Distribution**: Multi-platform single-file executables bundled via PyInstaller and published via GitHub Actions releases.

---

## Documentation Directory

| Document | Purpose |
| :--- | :--- |
| [System Architecture](docs/architecture/system-architecture.md) | High-level system blocks, data flow, and subsystem boundaries |
| [Protocol Schema Specification](docs/specs/protocol-schema-specification.md) | Formal specification of YAML/JSON protocol definition files |
| [Automation Script Specification](docs/specs/script-schema-specification.md) | Specification for automated test and command scripts |
| [Hardware & Virtual Transport Design](docs/design/transport-and-virtual-device.md) | Serial port management and virtual MCU simulation engine |
| [Dynamic Web UI Architecture](docs/design/dynamic-ui-architecture.md) | Schema-to-form generation and WebSocket streaming |
| [Standalone Packaging Design](docs/design/standalone-packaging.md) | PyInstaller compilation, asset bundling, and release pipeline |
| [Verification & Test Strategy](docs/testing/test-strategy.md) | Zero-defect verification policy, test matrices, and test vectors |
| [Release Guidance & User Manual](docs/release/guidance.md) | Installation, CLI commands, and quickstart guide |

---

## Quick Example: Protocol Definition

```yaml
schema_version: "1.0.0"
metadata:
  name: "BinarySensorNode"
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

## Project Structure

```
omni-uart/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Automated linting, validation & tests
│       └── release.yml            # Multi-OS standalone binary release builder
├── docs/
│   ├── architecture/              # System architecture documents
│   ├── specs/                     # Formal schema & script specifications
│   ├── design/                    # Detailed subsystem design documents
│   ├── testing/                   # Test strategy & test vector definitions
│   └── release/                   # Release guidance and user manuals
├── schemas/
│   ├── protocol.schema.json       # JSON schema for protocol definitions
│   └── script.schema.json         # JSON schema for automation scripts
├── examples/
│   ├── protocols/                 # Example YAML and JSON protocol specs
│   └── scripts/                   # Example YAML and JSON automation scripts
├── omniuart.spec                  # PyInstaller standalone build configuration
├── pyproject.toml                 # Modern PEP 621 Python package configuration
└── README.md
```

---

## License

OmniUART is licensed under the [MIT License](LICENSE).
