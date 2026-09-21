# OmniUART: Universal UART Protocol Tool

[![CI](https://github.com/markbac/omni-uart/actions/workflows/ci.yml/badge.svg)](https://github.com/markbac/omni-uart/actions/workflows/ci.yml)
[![Release](https://github.com/markbac/omni-uart/actions/workflows/release.yml/badge.svg)](https://github.com/markbac/omni-uart/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

> **Universal, schema-driven UART protocol tool for embedded systems, IoT devices, and hardware test engineering.**

## Core Capabilities
- **Schema-Driven Protocols**: Define binary, text, and hybrid UART protocols declaratively using JSON or YAML.
- **Three Operational Modes**:
  1. **Interactive CLI**: Send single commands, inspect structured responses, and sniff serial traffic.
  2. **Batch Script Runner**: Execute automated test sequences with timeouts, delays, and assertions.
  3. **Auto-Generated Web UI**: Zero-install local dashboard that dynamically generates command forms, parameter controls, and real-time streaming TX/RX packet inspectors.
- **Virtual MCU Loopback**: Test and validate protocols completely offline without requiring physical hardware.
- **Standalone Distribution**: Distributed as single-file standalone binaries for Windows, Linux, and macOS—no Python installation required.

---

## Documentation & Architecture
- [System Architecture](docs/architecture/system-architecture.md)
- [Protocol Schema Specification](docs/specs/protocol-schema-specification.md)
- [Script Schema Specification](docs/specs/script-schema-specification.md)
- [Hardware & Virtual Transport Design](docs/design/transport-and-virtual-device.md)
- [Dynamic UI Architecture](docs/design/dynamic-ui-architecture.md)
- [Standalone Packaging & Distribution](docs/design/standalone-packaging.md)
- [Verification & Test Strategy](docs/testing/test-strategy.md)
- [Release Guidance & User Manual](docs/release/guidance.md)
