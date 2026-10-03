# Changelog

All notable changes to the OmniUART project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Added `BackgroundDevice` (`omniuart.core.background`), a thread-safe controller that lets GUI clients use `DeviceSession` and `ScriptRunner`, and `CatalogManager.resolve_script_protocol`, shared by the CLI and desktop app (#254).
- Replaced the in-memory `WindowsNamedPipeTransport` stub with a genuine Windows named-pipe client/server transport on the asyncio Proactor loop (connect retry, timeouts, partial reads, back-pressure, peer-disconnect detection) and added `WindowsNamedPipePair`; Windows-specific integration tests run in the existing windows-latest CI job (#194).
- Added `PtyTransport` and rebuilt `PtySerialPair` on real pseudo-terminal descriptors: raw non-blocking event-loop I/O, timeouts, partial reads, endpoint lifecycle, peer-close detection, and an openable `slave_pts_path` that PySerial can use. Previously the PTY was allocated but never connected to the transports (#195).
- Added `ScriptRunner` (`omniuart.core.runner`), a reusable script execution engine with ordered steps, delays, log steps, send/receive with timeouts, assertions (operators and kit-format aliases), `${variables}` with `save`, abort-or-continue handling, optional recording and a JSON report (#193).
- Added script-level `variables` and step-level `save` to the script schema (#193).
- Added `DeviceSession` (`omniuart.core.session`) which encodes a command, transmits it, and decodes the response with timeouts, recording and typed outcomes; used by the CLI and shared with future clients (#192).
- Added `FrameCodec` (`omniuart.core.codec`), a schema-driven frame encoder, decoder and stream resynchroniser shared by every component, with strict value encoding for all field types, `uint8`/`uint16`/`uint32` length fields honouring `includes`, and real CRC integrity (#189).
- Added the optional `framing.integrity.covers` setting (`after_header`, `full_frame`, `payload_only`) to the protocol schema (#189).
- Documented the normative wire format in the protocol schema specification (#189).

### Changed
- **BREAKING:** The native desktop app now performs real I/O. Connect opens the chosen serial port (or the explicit `virtual` simulated device) and reports failures instead of flipping to "Connected"; Disconnect closes it. Sending encodes with `FrameCodec`, transmits and shows the decoded response, timeout or error. The Script Runner tab uses the shared `ScriptRunner` and shows real per-step and per-assertion results. The Telemetry Plotter plots only numeric fields decoded from valid RX frames (no longer TX bytes or regex/byte guesses, and with a real-value axis), and Auto-Poll is limited to `dashboard`-tagged commands with defaulted parameters. The invented port list and hard-coded AT/Modbus macros and poll payloads were removed. This replaces the unsupported "real live RX" claim in 2.0.0 with behaviour that matches it (#254).
- **BREAKING:** The web API no longer returns fabricated data. `POST /api/send`, `POST /api/script/run` and `GET /api/dashboard/auto-run` execute through the shared session, codec and runner and need an open connection (`409` otherwise); unknown protocols, commands and scripts return `404`, invalid parameters `422`, no response `504`, and a failing device a failing result. `POST /api/serial/connect` validates the baud rate, opens a real transport and fails with `400` for a port that cannot be opened; new `POST /api/serial/disconnect` and `GET /api/serial/status` endpoints; `/api/serial/ports` no longer invents ports. The simulated device is the explicit `virtual` port and every response from it says `"simulated": true`. The web UI shows a real connect/disconnect result (#253).
- **BREAKING:** `omni-uart run` now really executes the script instead of printing its steps: choose `--port <port>` or `--virtual`, optionally `--protocol`, `--record` and `--report`. Exit status is 0 all passed, 1 a step failed, 2 invalid script or input, 3 transport error (#193).
- **BREAKING:** `omni-uart send` now really transmits. Pick a transport with `--port <port>` or `--virtual`; `--dry-run` is an explicit option and no longer the default, and running `send` with none of them is an error. Exit status is 0 on success, 1 for no or invalid response, 2 for invalid input, 3 for transport failure (#192).

### Fixed
- `load_protocol` and `load_script` no longer fail with `OSError: File name too long` when given a long inline JSON/YAML document (#193).
- Desktop and CLI frame builder now uses `FrameCodec`: it writes the real configured CRC instead of a 16-bit byte sum, honours the declared length field width, encodes `uint64` and `int64` as binary, and rejects invalid or out-of-range parameters instead of clamping them or sending `0x00` (#255).
- Kit-format commands no longer expose their discriminator (for example AT command text) as a required parameter on delimited protocols; constant fields now carry their `constValue` as the default (#255).
- `HardwareSerialTransport` applies the protocol's byte size, parity, stop bits and flow control, accepts PySerial URLs, and honours per-read timeouts (#192).
- Generic binary simulator and `VirtualTransport` no longer assume the command ID is at byte 4 or reply with a fixed frame: requests are parsed and identified by `FrameCodec`, responses are built from the protocol's `response` definitions, invalid or unanswerable frames are ignored, and the simulator replies once per frame instead of once per received byte (#190).
- Fuzzer now builds vectors with `FrameCodec` and reports explicit outcomes (`ACCEPTED`, `CORRECTLY_REJECTED`, `UNEXPECTEDLY_ACCEPTED`, `MALFORMED_RESPONSE`, `TIMEOUT`, `HANG`, `TRANSPORT_ERROR`) using a liveness probe to detect hangs; the `fuzz` CLI command exits non-zero unless every vector was handled correctly (#191).
- `VirtualTransport.read` keeps surplus bytes for the next read instead of discarding them, and the simulator ignores out-of-range parameters and abandons incomplete frames after an idle timeout (#191).

## [2.0.0] - 2026-09-27

### Added
- Added Global Active Protocol selector dropdown in `ConnectionToolbar` defaulting to `None`, synced across all tabs, auto-filling baudrate, data bits, parity, stop bits from spec (#171, #173).
- Added multi-line multi-channel telemetry plotter with configurable command selector (`AT Ping`, `CSQ`, `CBC`, Modbus, active spec commands), frequency interval selector (`100 ms` to `5.0 s`), auto-polling controller timer (`▶ Start Auto-Poll` / `⏹ Stop Polling`), multi-line waveform rendering (`Line 1 Cyan`, `Line 2 Green`), dynamic statistical summary metrics (Min, Max, Avg, Latest), and channel legend badges (#172, #174, #179, #180).
- Overhauled GitHub Pages documentation site as a dedicated "About OmniUART" landing page with a structured MkDocs and npm AsyncAPI 2.6.0 protocol catalog hub (#175, #176, #181, #182).

### Changed
- Connected Telemetry Plotter waveform chart directly to real live serial RX byte payloads, eliminating synthetic data (#177, #178).
- Updated static documentation generator fallback in `docs_generator.py` to serve root About OmniUART landing page and generate `protocols/index.html` (#181, #182).

## [1.9.0] - 2026-09-27

### Added
- Added dynamic serial port refresh button `🔄` to native desktop `ConnectionToolbar` and REST API `/api/ports` endpoint (#159).
- Added live stream session recording (`🔴 Record Stream`) and text log export (`💾 Export Log`) controls to `CommsStreamerView` (#160).
- Added IoT quick action macro shortcut buttons (`⚡ AT Ping`, `📶 Signal CSQ`, `🔋 Battery CBC`, `🌐 Network CREG?`, `⚙️ Modbus Read`) to `CommsStreamerView` (#161).

## [1.8.0] - 2026-09-27

### Added
- Added external protocol schema directory loading in `CatalogManager` relative to binary location and working directory (#149).
- Enhanced binary smoke test suite (`test_simulator_back_to_back.py`, `test_binary_smoke.py`) to test CLI, Web UI, Desktop UI, and Simulator against each other (#151).

### Changed
- Excluded protocol schemas and examples from embedded PyInstaller binary assets in `omniuart.spec` and packaged them as external editable release assets in release workflow (#150).

## [1.7.0] - 2026-09-27

### Added
- Added active protocol selector dropdown to Dashboard and Command Catalog views (#140).
- Enhanced Comms Streamer with dual raw hex and decoded semantic packet field view (#141).
- Bundled Virtual MCU Simulator executable (`omni-uart-simulator`) and `start-simulated-workspace.ps1` quickstart script in releases (#142).

### Fixed
- Fixed string discriminator formatting exception `ValueError: invalid format string` in frame payload builder (#139).

## [1.6.0] - 2026-09-27

### Added
- Integrated Vale, Markdownlint, `.vale.ini`, `.markdownlint.yaml`, and `Embedded` style rules from `docs-check` into `scripts/check_docs.py` and CI pipeline (#133).

### Fixed
- Fixed FastAPI Web UI server launcher to enforce strict `127.0.0.1` loopback binding (#131).
- Fixed desktop frame payload builder with parameter min/max range bounds checking and numeric type casting safety (#132).

## [1.5.0] - 2026-09-27

### Added
- Created root `CHANGELOG.md` adhering to the Keep a Changelog 1.1.0 specification (#125, #126).
- Implemented CORS security middleware restricting Web UI access to local loopback origins (#128).
- Created `SECURITY.md` detailing security architecture, CORS middleware, input sanitization, and vulnerability reporting procedures (#128).
- Updated README.md and documentation suite to reflect the 3 dedicated standalone executables (CLI, Web UI, Native Desktop UI) and security controls (#129).

### Changed
- Refactored `scripts/generate_release_notes.py` to output Keep a Changelog 1.1.0 complaint markdown sections (`Added`, `Changed`, `Fixed`, `Security`) (#127).

### Security
- Enforced strict CORS origin controls (`http://127.0.0.1:8000`, `http://localhost:8000`) and loopback binding on FastAPI Web UI server (#128).

## [1.4.0] - 2026-09-27

### Added
- Implemented 100% native standalone Tkinter/TTK Desktop GUI application (`omni-uart-desktop`) replacing PyWebView wrapper (#119).
- Added Physical Serial Connection Toolbar with port selection, baud rates up to 921600 bps, parity, stop bits, and live connection status indicator (#120).
- Built native Command Catalog Treeview with dynamic parameter form controls, discriminator tags, and physical unit labels (`°C`, `mV`, `hPa`) (#121).
- Added real-time Canvas Telemetry Line Plotter tab, Automation Script Runner tab, and Raw Comms Streamer tab (#122).
- Added native desktop unit tests (`test_desktop_native.py`) (#123).

### Changed
- Updated `desktop_main.py` entrypoint and PyInstaller build spec (`omniuart.spec`) to package native Tkinter GUI without PyWebView overhead (#123).

## [1.3.0] - 2026-09-27

### Added
- Added automated issue-based release notes generator script (`scripts/generate_release_notes.py`) to release workflow (#115-#117).

## [1.2.0] - 2026-09-27

### Added
- Added PyInstaller compilation and runtime startup smoke tests to CI pipeline (`.github/workflows/ci.yml`) and release workflow (`.github/workflows/release.yml`) (#111-#113).
- Created 3 dedicated entrypoint modules and standalone binary targets (`omni-uart-cli`, `omni-uart-web`, `omni-uart-desktop`) (#108-#110).

## [1.1.1] - 2026-09-27

### Fixed
- Fixed PyInstaller frozen binary uvicorn app instance import error (`ModuleNotFoundError: No module named 'omniuart.ui'`, Issue #106).

## [1.1.0] - 2026-09-27

### Added
- Added PyWebView desktop window launcher and `--mode desktop` CLI flag (#102-#104).

## [1.0.0] - 2026-09-27

### Added
- Initial release of OmniUART schema-driven protocol engine with interactive CLI, batch runner, and FastAPI Web UI.

[2.0.0]: https://github.com/markbac/omni-uart/compare/v1.9.0...v2.0.0
[1.9.0]: https://github.com/markbac/omni-uart/compare/v1.8.0...v1.9.0
[1.6.0]: https://github.com/markbac/omni-uart/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/markbac/omni-uart/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/markbac/omni-uart/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/markbac/omni-uart/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/markbac/omni-uart/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/markbac/omni-uart/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/markbac/omni-uart/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/markbac/omni-uart/releases/tag/v1.0.0
