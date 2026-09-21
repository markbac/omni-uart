# Contributing & Development Standards

Welcome to the **OmniUART** project. To ensure zero defects, predictable release engineering, and clear historical changelogs, all contributions and automated pipelines strictly enforce **Semantic Versioning** and **Conventional Commits**.

---

## 1. Semantic Versioning (SemVer 2.0.0)

OmniUART strictly adheres to [Semantic Versioning 2.0.0](https://semver.org/):

$$\text{Version} = \text{MAJOR}.\text{MINOR}.\text{PATCH}$$

| Segment | Increment Trigger | Example |
| :--- | :--- | :--- |
| **MAJOR** | Incompatible API changes, breaking schema modifications, removed CLI flags, or protocol breaking changes. | `1.0.0` $\to$ `2.0.0` |
| **MINOR** | Backwards-compatible new features, new protocol field types, new CLI commands, new UI capabilities. | `0.1.0` $\to$ `0.2.0` |
| **PATCH** | Backwards-compatible bug fixes, minor performance improvements, internal refactoring. | `0.1.0` $\to$ `0.1.1` |

### 1.1 Pre-Release & Build Identifiers
- **Alpha / Beta / Release Candidate**: `1.0.0-alpha.1`, `1.0.0-rc.2`
- **Release Tags**: Git tags must be prefixed with `v`: e.g. `v0.1.0`, `v1.0.0`.
- Pushing a tag matching `v*.*.*` automatically triggers the GitHub Actions standalone release workflow.

### 1.2 Logical Use of Semantic Version Build Metadata (`+<metadata>`)
Per SemVer 2.0.0 (Rule 10), build metadata is denoted by appending a plus sign `+` followed by dot-separated alphanumeric identifiers `[0-9A-Za-z-]`. **Build metadata MUST NOT affect version precedence**, but is leveraged in OmniUART to provide critical engineering traceability across hardware revisions and build pipelines.

#### A. Tool & Standalone Executable Binaries
- **Commit Binding**: `0.1.0+git.5948e11` (embeds the exact git commit hash in the binary).
- **CI Build Run & Platform**: `0.1.0+build.42.win64` (links the binary to the CI runner pipeline execution).
- **Timestamp Binding**: `0.1.0+20260921` (documents compilation date).
- **Runtime Verification**: Running `omni-uart --version` reports:
  `omni-uart 0.1.0+git.5948e11 (x86_64-pc-windows-msvc, built 2026-09-21)`

#### B. Protocol Specifications (`metadata.version`)
In embedded systems, protocols evolve in tandem with hardware revisions and firmware versions. Protocol specifications use logical metadata to establish device compatibility:
- **Hardware Board Revision Binding**: `1.2.0+hw.revB` (denotes protocol version 1.2.0 verified on PCB Hardware Revision B).
- **Firmware Baseline Binding**: `2.0.0+fw.3.4.1` (denotes protocol version 2.0.0 compatible with device Firmware 3.4.1).
- **Hybrid Traceability**: `1.1.0+hw.revB.fw.2.0.1` (comprehensive hardware and firmware compatibility tag).

#### C. Script Specifications (`version`)
- **Suite Tagging**: `1.0.0+suite.thermal.hwB` (binds automated test script to specific validation test fixtures).

---

## 2. Conventional Commits (v1.0.0)

All commit messages and Pull Request titles must follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification:

```
<type>(<scope>): <short description in imperative mood>

[optional body providing technical rationale and detailed deliverable list]

[optional footer(s) for breaking changes or issue references]
```

### 2.1 Allowed Types
| Type | Purpose | Example |
| :--- | :--- | :--- |
| **`feat`** | A new feature or capability | `feat(codec): add bitfield unpacker support` |
| **`fix`** | A bug fix | `fix(crc): resolve 16-bit reflection bitmask overflow` |
| **`docs`** | Documentation only changes | `docs(specs): add NMEA sentence framing guide` |
| **`refactor`** | Code changes that neither fix a bug nor add a feature | `refactor(transport): extract queue reader worker` |
| **`perf`** | Code change that improves performance | `perf(crc): precompute 256-entry lookup table` |
| **`test`** | Adding missing tests or correcting existing tests | `test(stream): add 2KB random noise recovery test` |
| **`build`** | Changes that affect packaging, PyInstaller, or dependencies | `build(pyinstaller): add uvicorn hidden imports` |
| **`ci`** | Changes to CI/CD workflows and configuration scripts | `ci(actions): matrix across Windows and Linux` |
| **`chore`** | Maintenance tasks, standards, repo scaffolding | `chore(standards): establish conventional commits` |
| **`revert`** | Reverts a previous commit | `revert: feat(ui): revert broken slider component` |

### 2.2 Standard Scopes
Use one of the established architectural scopes:
- **`core`**: Core engine, framing, codec, and models.
- **`codec`**: Dynamic field packer/unpacker and stream sync hunter.
- **`crc`**: Zero-dependency CRC and checksum algorithms.
- **`transport`**: Hardware serial port (`pyserial`) and Virtual MCU simulator.
- **`runner`**: Automated batch script runner and assertion evaluator.
- **`cli`**: Typer and Rich command-line interface.
- **`ui`**: Web dashboard, Comms Panel, and WebSocket streaming bridge.
- **`recorder`**: Session recording ring buffer and data exporters (JSONL/CSV/BIN).
- **`spec`**: Formal YAML/JSON protocol and script schemas.
- **`packaging`**: PyInstaller standalone executable bundling.
- **`release`**: Release automation and guidance docs.

### 2.3 Breaking Changes
A breaking change must be indicated by an exclamation mark `!` before the colon or a `BREAKING CHANGE:` footer:

```git
feat(spec)!: change header bytes representation from array to hex string

BREAKING CHANGE: The 'header' field in protocol framing now requires a hex string (e.g. '0xAA55') instead of an integer array.
```

---

## 3. Branching & Pull Request Workflow

1. **Branch Off `main`**:
   - Format: `<type>/<short-topic-description>`
   - Examples:
     - `feat/crc-engine`
     - `fix/sync-hunt-slip`
     - `docs/authoring-guide`
     - `chore/semver-and-conventional-commits`
2. **Docs-as-Code & Automated Test Requirement**:
   - Zero-defect policy: every feature branch must include corresponding unit tests and documentation updates.
3. **Pull Request Title**:
   - The PR title must strictly follow Conventional Commits (e.g. `feat(core): implement zero-dependency CRC engine`).
4. **Squash & Merge**:
   - Merge branches via squash commits to keep `main` history clean, atomic, and linear.
