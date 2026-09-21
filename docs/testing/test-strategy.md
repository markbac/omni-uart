# OmniUART Verification & Test Strategy

## 1. Zero-Defect Policy
In accordance with system reliability standards, **no code is merged to `main` without automated test suite verification**. Every subsystem in OmniUART must be covered by deterministic unit, integration, and regression test suites that execute in headless continuous integration.

---

## 2. Test Architecture & Directory Structure

```
tests/
├── unit/
│   ├── test_crc.py              # Zero-dependency CRC & checksum test vectors
│   ├── test_models.py           # Protocol & script schema validation models
│   ├── test_codec_pack.py       # Command serialization and field packing
│   ├── test_codec_stream.py     # Stream parser, sync hunt, noise resilience
│   └── test_virtual_mcu.py      # Virtual loopback transport & fault injection
├── integration/
│   ├── test_script_runner.py    # Multi-step script execution & assertions
│   ├── test_cli.py              # CLI command execution via Typer CliRunner
│   └── test_web_api.py          # FastAPI endpoints & WebSocket communication
└── e2e/
    └── test_standalone_smoke.py # Standalone PyInstaller executable smoke tests
```
[[CAPTION:Figure]] Test suite organization.

---

## 3. Test Suites & Verification Criteria

### 3.1 CRC & Integrity Test Vectors (`test_crc.py`)
Standard test vectors must match established IEEE and industrial specifications:

| Algorithm | Test Vector Input | Expected Hex Output | Reference Standard |
| :--- | :--- | :--- | :--- |
| `CRC-8 (SMBus)` | `"123456789"` (ASCII bytes) | `0xF4` | SMBus 3.0 / ITU-T I.432.1 |
| `CRC-16/Modbus` | `"123456789"` (ASCII bytes) | `0x4B37` | Modbus Serial Line Protocol v1.02 |
| `CRC-16/CCITT-False` | `"123456789"` (ASCII bytes) | `0x29B1` | X.25 / ISO 3309 |
| `CRC-32 (IEEE 802.3)` | `"123456789"` (ASCII bytes) | `0xCBF43926` | IEEE 802.3 Ethernet |
| `Sum8` | `[0x01, 0x02, 0x03, 0x04]` | `0x0A` | Modulo 256 sum |
| `XOR (LRC)` | `[0xAA, 0x55, 0x01]` | `0xFE` | Longitudinal Redundancy Check |
| `Custom Rocksoft CRC` | Arbitrary `poly`, `init`, `refin`, `refout`, `xorout` | Matching `check` field | Rocksoft Model Parameter Spec |

[[CAPTION:Table]] Standard and custom test vectors for the integrity engine.

### 3.2 Codec & Stream Resilience Testing (`test_codec_stream.py` & `test_dissector.py`)
- **Noise Resilience**: The stream decoder is fed 2048 bytes of pseudorandom noise followed by a valid protocol frame. The decoder must successfully locate the sync header and decode the message without dropping or corrupting the payload.
- **Partial Frame Splitting**: Frames are delivered to the decoder in 1-byte increments over multiple read cycles. The parser must buffer the fragments and yield the frame once the footer is received.
- **Corrupted CRC Rejection & Diagnostics**: Frames with corrupted checksum bytes must be flagged with `crc_valid=False`, with diagnostic payload highlighting the mismatched byte offset and expected vs received CRC.
- **Byte Dissection Slices**: Verifies that every byte slice in a frame (Header, Length, Command ID, Payload, CRC, Footer) is accurately delineated with zero off-by-one errors.

### 3.3 Session Recorder & Data Persistence (`test_recorder.py`)
- Verifies real-time event buffering of bidirectional traffic (`tx` / `rx`) with microsecond timestamp fidelity.
- Verifies round-trip serialization and export:
  - **JSON Lines (`.jsonl`)**: Validates line-by-line JSON parsing with all metadata intact.
  - **CSV (`.csv`)**: Validates tabular headers, timestamp formatting, and escaped field payloads.
  - **Raw Binary (`.bin`)**: Validates bit-for-bit reconstruction of physical UART traffic.

### 3.4 Virtual Transport & Script Runner Tests (`test_script_runner.py`)
- Executes complete test sequences against the virtual MCU loopback.
- Tests assertion logic across all operators (`==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `tolerance`).
- Verifies that `abort_on_error: true` halts the sequence immediately on failure, while `abort_on_error: false` logs failures and proceeds to completion.

### 3.5 Standalone Executable Verification (`test_standalone_smoke.py`)
On each GitHub Actions runner OS:
- Executes `omni-uart --version` and asserts exit code `0`.
- Executes `omni-uart validate examples/protocols/binary_sensor_node.yaml` and asserts schema validity.
- Executes `omni-uart validate examples/protocols/custom_crc_device.yaml` and asserts custom CRC schema validity.
- Executes `omni-uart run examples/scripts/sensor_test_suite.yaml --virtual` and asserts all tests pass.

---

## 4. Test Execution Commands

```bash
# Execute full unit and integration test suite
pytest tests/ -v --tb=short --cov=omniuart --cov-report=term-missing

# Run CRC test vector verification only
pytest tests/unit/test_crc.py -v

# Run stream decoder noise resilience tests
pytest tests/unit/test_codec_stream.py -v
```
[[CAPTION:Figure]] Test execution commands.
