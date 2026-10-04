# OmniUART: Universal Schema-Driven UART Protocol Tool

[![CI](https://github.com/markbac/omni-uart/actions/workflows/ci.yml/badge.svg)](https://github.com/markbac/omni-uart/actions/workflows/ci.yml)
[![Release](https://github.com/markbac/omni-uart/actions/workflows/release.yml/badge.svg)](https://github.com/markbac/omni-uart/actions/workflows/release.yml)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![SemVer](https://img.shields.io/badge/SemVer-2.0.0-green.svg)](https://semver.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

> **Universal, schema-driven UART protocol tool for embedded systems, IoT devices, and hardware test engineering.**

OmniUART decouples protocol definitions from custom tooling code by using declarative JSON or YAML specifications. It provides an ad-hoc CLI, an automated test runner with assertions, a dynamic Web UI, and a 100% native desktop GUI workspace.

Distributed as **standalone executables** for Windows and Linux—no Python installation required:
- `omni-uart-cli`: Command Line Interface for batch automation and quick ad-hoc commands.
- `omni-uart-web`: Browser-based Dynamic Web UI with WebSockets streaming.
- `omni-uart-desktop`: 100% Native Tkinter/TTK Desktop Application workspace.

---

## Key Features

- **Schema-Driven Protocols (JSON/YAML)**: Define message envelopes, sync preambles, dynamic length fields, opcodes, typed payloads (integers, floats, enums, strings, booleans), and footers.
- **Custom Parametric CRC & Presets**: Pure-Python, zero-dependency integrity engine supporting standard presets (CRC8, CRC16-Modbus, CRC16-CCITT, CRC32, Sum, XOR) and **fully custom parametric CRCs** via the Rocksoft Model (`width`, `poly`, `init`, `refin`, `refout`, `xorout`, `endian`).
- **Dual-View Raw & Decoded Stream Inspector**: Real-time side-by-side visualization of raw hexadecimal bytes and structured decoded payload fields.
- **Session Recording & Export**: Record full serial transactions with microsecond timestamps and export to JSON Lines (`.jsonl`), CSV, raw binary (`.bin`), or Wireshark PCAPNG (`.pcapng`) for post-session analysis or automated playback.
- **Standalone Executables**:
  1. **omni-uart-cli**: Send commands, format parameters, and decode responses on the command line.
  2. **omni-uart-web**: Local web interface (FastAPI + WebSockets) that dynamically builds forms for any loaded protocol, streams decoded frames, and provides session controls.
  3. **omni-uart-desktop**: Native Tkinter/TTK desktop application with physical serial connection controls, command catalog tree, canvas line chart plotter, script runner, and comms streamer.
- **Virtual MCU Simulation**: Test protocols and execute regression suites completely offline without physical hardware attached.
- **Security Safeguards**: Local loopback (`127.0.0.1`) binding, strict Host/Origin checking, Pydantic input validation, and zero external web runtime dependencies.
- **Docs-as-Code & Comprehensive Testing**: Formal specifications, schemas, and comprehensive unit and integration test suites.

---

## Documentation Directory

| Document | Purpose |
| :--- | :--- |
| [Changelog](CHANGELOG.md) | Release history complying with Keep a Changelog 1.1.0 |
| [Security Policy](SECURITY.md) | Security architecture, CORS controls, and vulnerability reporting |
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
│       ├── ci.yml                 # Automated linting, validation & binary smoke tests
│       └── release.yml            # Multi-OS standalone binary release builder
├── docs/                          # Architecture specs and release guidance
├── schemas/                       # JSON schemas for protocol and script validation
├── examples/                      # Example protocol definitions (UBX, MAVLink, SCPI, Modbus, XBee, HCI)
├── src/omniuart/
│   ├── cli.py                     # CLI parsing and command execution
│   ├── desktop/                   # Native Tkinter/TTK Desktop Application
│   ├── entrypoints/               # Executable entry points (cli_main, web_main, desktop_main)
│   ├── ui/                        # Web UI FastAPI/Uvicorn routes and templates
│   └── core/                      # Schema parser, framing builder, CRC engine, transports
├── CHANGELOG.md                   # Keep a Changelog 1.1.0 log
├── SECURITY.md                    # Security safeguards policy
├── omniuart.spec                  # PyInstaller multi-target build spec
├── pyproject.toml                 # PEP 621 Python project configuration
└── README.md
```

---

## Contributing & Standards

OmniUART strictly enforces **Semantic Versioning 2.0.0**, **Keep a Changelog 1.1.0**, and **Conventional Commits 1.0.0**. All changes are delivered via scoped feature branches and Pull Requests merged into `main`.

For commit conventions, scopes, branch naming, and release procedures, please refer to [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License & Authorship

OmniUART is copyright © 2026 **Mark Bacon** and licensed under the [MIT License](LICENSE).

> **AI Collaboration Statement**: OmniUART was architected, developed, and verified in pair-programming collaboration between Mark Bacon and AI autonomous coding agents (Google Antigravity). All legal copyright and rights are held by Mark Bacon under the MIT License.
