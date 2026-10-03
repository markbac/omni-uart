# Security Policy & Architecture Safeguards

## Supported Versions

The following versions of OmniUART receive active security updates and patch maintenance:

| Version | Supported          |
| ------- | ------------------ |
| 1.5.x   | :white_check_mark: |
| 1.4.x   | :white_check_mark: |
| < 1.4.0 | :x:                |

## Security Controls & Architecture

OmniUART implements defensive safeguards across all physical hardware serial interfaces, REST API endpoints, WebSocket streams, and native GUI applications:

1. **Local Network Interface Isolation**:
   - Web UI server only listens on a loopback address; any other `--host` is replaced by `127.0.0.1` with a warning on stderr.
   - Every HTTP request and WebSocket upgrade is rejected (403) unless its `Host` is `localhost`, `127.0.0.1` or `::1`, which blocks DNS rebinding; a browser `Origin` header must be one of those too, which blocks cross-site WebSocket and write requests. CORS allows loopback origins on any port.
   - There is no login or session token yet: other processes running as the same user on this machine can still call the API.

2. **Input Validation & Type Safety**:
   - All inbound protocol command payloads and hardware parameter signatures are validated using Pydantic v2 schemas.
   - Out-of-bounds parameter values (integers, floats, enums, data rates) are rejected before bytes are transmitted over physical serial interfaces.

3. **Subprocess & Execution Security**:
   - PyInstaller frozen executables (`omni-uart-cli`, `omni-uart-web`, `omni-uart-desktop`) execute within isolated sandboxed process boundaries.
   - Dynamic schema loader verifies absolute path resolution to prevent directory traversal attacks.

## Reporting a Vulnerability

If you discover a potential security vulnerability in OmniUART, please report it via GitHub Private Vulnerability Reporting or contact the maintainers directly. Do not file public issue reports for unpatched zero-day vulnerabilities.
