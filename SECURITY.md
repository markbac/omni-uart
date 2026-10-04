# Security Policy & Architecture Safeguards

## Supported Versions

The following versions of OmniUART receive active security updates and patch maintenance:

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | :white_check_mark: |
| < 2.0.0 | :x:                |

## Security Controls & Architecture

OmniUART implements defensive safeguards across physical hardware serial interfaces, REST API endpoints, WebSocket streams, and native GUI applications:

1. **Local Network Interface Isolation**:
   - Web UI server defaults to loopback binding (`127.0.0.1`); binding to external interfaces is explicitly restricted unless specified.
   - HTTP requests and WebSocket upgrades check `Host` and `Origin` headers to protect against DNS rebinding and unauthorized cross-site requests.
   - Note: OmniUART runs locally without external authentication; other processes running under the local user session can access local endpoints.

2. **Input Validation & Type Safety**:
   - All inbound protocol command payloads and hardware parameter signatures are validated using Pydantic v2 schemas.
   - Out-of-bounds parameter values (integers, floats, enums, data rates) are validated against schema constraints before transmission over serial interfaces.

3. **Executable & Execution Boundaries**:
   - PyInstaller standalone executables (`omni-uart-cli`, `omni-uart-web`, `omni-uart-desktop`) bundle runtime dependencies into standalone binaries.
   - Dynamic schema loader parses validated JSON and YAML definitions within registered catalog directories.

## Reporting a Vulnerability

If you discover a potential security vulnerability in OmniUART, please report it via GitHub Private Vulnerability Reporting or contact the maintainers directly. Do not file public issue reports for unpatched zero-day vulnerabilities.
