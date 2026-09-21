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
