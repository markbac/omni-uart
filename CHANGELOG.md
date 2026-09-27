# Changelog

All notable changes to the OmniUART project will be documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.5.0]: https://github.com/markbac/omni-uart/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/markbac/omni-uart/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/markbac/omni-uart/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/markbac/omni-uart/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/markbac/omni-uart/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/markbac/omni-uart/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/markbac/omni-uart/releases/tag/v1.0.0
