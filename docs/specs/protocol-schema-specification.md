# OmniUART Protocol Schema Specification

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML Spec](asyncapi/omniuart-protocol-schema.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/omniuart-protocol-schema.html)

## 1. Specification Scope
This document formally defines the **OmniUART Protocol Specification Schema** (Version 1.0.0). Protocol definitions can be authored in either YAML or JSON and must conform to the structure documented herein.

The schema governs:
- Protocol metadata and communication parameters.
- Framing rules (binary synchronization preambles, dynamic length fields, integrity algorithms, and footers).
- Payload structure and parameterized command specifications.
- Telemetry and unsolicited notification structures.

---

## Resource limits

Untrusted definitions, scripts, captures and streams are bounded. Defaults, each overridable with the environment variable `OMNIUART_MAX_<NAME>` (a non-positive or non-numeric value is ignored with a warning):

| Limit | Default | Applies to |
|---|---|---|
| `DEFINITION_BYTES` | 1048576 | size of a protocol or script file or text; a document nested too deeply to parse is also an error |
| `FRAME_BYTES` | 1048576 | largest frame the codec waits for (a longer declared length is treated as a false header) and largest declared field `length` |
| `SCRIPT_STEPS` | 10000 | steps in a script |
| `SCRIPT_DURATION_S` | 3600 | wall-clock time of one script run; later steps are reported as an error then skipped |
| `REPLAY_DURATION_S` | 3600 | total waiting time of a session replay |
| `FUZZ_VECTORS` | 10000 | vectors in one fuzz campaign |
| `RETRIES` | 10 | retries of a telemetry webhook |

## Authoritative definition

The Pydantic models in `omniuart.core.models` are the canonical definition of the native protocol and script formats. `schemas/protocol.schema.json` and `schemas/script.schema.json` are generated from them (`python -m omniuart.schema_export`) and a test fails if the committed files drift. A JSON Schema cannot express every rule the models enforce (for example the CRC width and polynomial checks or the discriminator rules), so the models, and `omni-uart lint`, decide validity; the schema is for editor completion and early structural checks. The kit format (`uart-interface.schema.json`) is a separate, externally defined schema read through the kit adapter.

## 2. Top-Level Schema Structure

> **Important:** Unknown keys are errors. A misspelled or unsupported key (for example `comands`, `sufix` or `safty`) in a protocol or script makes loading and `lint` fail with the key's location, instead of being ignored. This applies to every section of both native formats.

A valid protocol specification contains four root sections:
1. `metadata`: Identification and documentation properties.
2. `serial_config`: Default hardware serial communication parameters.
3. `framing`: Framing, envelope, and integrity calculation parameters.
4. `commands`: Catalog of outbound commands and their corresponding response structures.
5. `telemetry` *(optional)*: Catalog of inbound unsolicited frames or periodic sensor telemetry.

```yaml
schema_version: "1.0.0"
metadata:
  name: "SampleProtocol"
  version: "1.2.0"
  description: "Demonstration protocol definition"
  author: "Embedded Systems Engineering"

serial_config:
  baudrate: 115200
  bytesize: 8
  parity: "none"
  stopbits: 1
  flow_control: "none"
  timeout_ms: 1000

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
  footer: [0x0D, 0x0A]

commands: []
telemetry: []
```
[[CAPTION:Figure]] Root structure of an OmniUART protocol specification.

---

## 3. Section Specifications

### 3.1 `metadata`
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | string | Yes | Short alphanumeric identifier for the protocol. |
| `version` | string | Yes | Semantic version string (e.g. `1.0.0`). |
| `description`| string | No | High-level summary of device/protocol functionality. |
| `author` | string | No | Author or maintainer name/team. |

[[CAPTION:Table]] Metadata specification fields.

### 3.2 `serial_config`
| Field | Type | Default | Permitted Values |
| :--- | :--- | :--- | :--- |
| `baudrate` | integer | `115200` | Any positive integer. Rates outside the common set (1200 to 921600, plus 250000) log a warning but are accepted. |
| `bytesize` | integer | `8` | `5`, `6`, `7`, `8`. |
| `parity` | string | `"none"` | `"none"`, `"even"`, `"odd"`, `"mark"`, `"space"`. |
| `stopbits` | number | `1` | `1`, `1.5`, `2`. |
| `flow_control`| string | `"none"` | `"none"`, `"hardware"` (RTS/CTS), `"software"` (XON/XOFF). |
| `timeout_ms` | integer | `1000` | Response timeout in milliseconds. |

[[CAPTION:Table]] Serial port default parameters.

### 3.3 `framing`
OmniUART supports two primary framing modes: **`binary`** and **`delimited`** (ASCII/text).

#### 3.3.1 Binary Framing Parameters
| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | string | Must be `"binary"`. |
| `header` | list[int] \| hex | Sync pattern prefix (e.g. `[0xAA, 0x55]` or `0xAA55`). |
| `length` | object | Length field descriptor (see below). |
| `command_id`| object | Command ID descriptor (type, endian). |
| `integrity` | object | Checksum/CRC configuration. |
| `footer` | list[int] \| hex | Optional trailer sequence (e.g. `[0x55, 0xAA]`). |

[[CAPTION:Table]] Binary framing specification fields.

The `length` object defines how frame length is determined:
- `type`: `uint8`, `uint16`, `uint32`.
- `endian`: `"little"` or `"big"`.
- `includes`:
  - `"payload_only"`: Value equals length of parameter payload.
  - `"payload_and_cmd"`: Value equals parameter payload + command ID byte(s).
  - `"full_frame"`: Value equals complete frame byte length including headers and CRC.

#### 3.3.2 Delimited Framing Parameters
| Field | Type | Description |
| :--- | :--- | :--- |
| `type` | string | Must be `"delimited"`. |
| `prefix` | string | Optional command prefix (e.g. `"AT+"` or `"$"`). |
| `delimiter` | string | Parameter delimiter (e.g. `","` or `"="`). |
| `suffix` | string | End of line sequence (e.g. `"\r\n"` or `"\n"`). |
| `integrity` | object | Optional ASCII checksum (e.g. NMEA XOR checksum). |

[[CAPTION:Table]] Delimited framing specification fields.

#### 3.3.3 Wire Format (Normative)
All OmniUART components build and parse frames through one codec (`omniuart.core.codec.FrameCodec`), so the rules below apply identically to the CLI, web API, desktop GUI, simulator, fuzzer and script runner.

A binary frame is laid out in this order. Every part except the payload is optional and present only when the matching `framing` key is declared:

```text
header | length | command_id | payload | integrity | footer
```

- **Length**: encoded with the declared `length.type` (`uint8`, `uint16`, `uint32`) and `length.endian`. `includes` selects what the value counts: the payload only, the payload plus command ID, or the whole frame.
- **Command ID**: `command_id.type` (`uint8`, `uint16`, `uint32`) and `command_id.endian`.
- **Payload**: fields in declaration order, each encoded with its own `endian`. Integers use their natural width, `uint64`/`int64` are 8 bytes (not text), `bool` and `enum` are one byte, `string` and `bytes` use `length` when declared (shorter values are zero padded, longer values are rejected) and otherwise consume the rest of the payload, so they must be the last field.
- **Integrity**: the checksum is sized by the algorithm (`crc8`, `sum8`, `xor` are 1 byte, 16-bit algorithms are 2, `crc32` is 4, `custom` uses `width`) and written with `integrity.endian`. `integrity.covers` selects the bytes it is calculated over:

| `covers` | Bytes covered |
| :--- | :--- |
| `after_header` (default) | Everything after the header up to the integrity field (length, command ID and payload). |
| `full_frame` | The header and everything after it up to the integrity field. |
| `payload_only` | The payload only. |

- **Footer**: appended verbatim.

Delimited frames are `prefix`, the command ID, each parameter preceded by `delimiter`, then `suffix`. Integrity on delimited frames is not applied.

> **Important:** Encoding is strict. A missing parameter without a `default`, an unknown parameter name, a value outside `min`/`max`, a value that does not fit the field type, or an `enum` value not listed in `options` is an error. Values are never clamped or replaced with `0x00`. The `scale` attribute is informational and is not applied by the codec.

When decoding a byte stream the codec discards bytes before a header (resynchronisation), keeps partial frames until more bytes arrive, and reports a frame with a bad integrity value, unknown ID or malformed payload as an invalid frame rather than dropping it silently.

### 3.4 Supported Data Types
Individual command parameters and response fields support the following primitive types:

| Data Type | Byte Size | Supported Attributes |
| :--- | :--- | :--- |
| `uint8`, `uint16`, `uint32`, `uint64` | 1, 2, 4, 8 | `endian`, `min`, `max`, `default`, `unit`, `scale` |
| `int8`, `int16`, `int32`, `int64` | 1, 2, 4, 8 | `endian`, `min`, `max`, `default`, `unit`, `scale` |
| `float32`, `float64` | 4, 8 | `endian`, `precision`, `min`, `max`, `default`, `unit` |
| `bool` | 1 | `default` |
| `enum` | 1, 2, 4 | `endian`, `options` (dictionary of numeric values to string labels) |
| `string` | dynamic / fixed | `encoding` (utf-8, ascii), `max_length`, `null_terminated` |
| `bytes` | dynamic / fixed | `length` |

[[CAPTION:Table]] Supported primitive field data types.

---

## 4. Integrity & CRC Algorithms

OmniUART provides a versatile, zero-dependency integrity engine supporting both standard industry presets and **fully custom parametric CRCs**.

### 4.1 Standard Preset Algorithms
The following named presets can be declared directly:

| Algorithm Identifier | Description | Polynomial | Initial Value | RefIn | RefOut | XOR Out | Endian |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `none` | No integrity validation | N/A | N/A | N/A | N/A | N/A | N/A |
| `sum8` | Simple 8-bit additive modulo 256 | N/A | `0x00` | No | No | `0x00` | N/A |
| `sum16` | 16-bit additive modulo 65536 | N/A | `0x0000` | No | No | `0x0000` | `little` / `big` |
| `xor` | 8-bit longitudinal redundancy check | N/A | `0x00` | No | No | `0x00` | N/A |
| `crc8` | Standard CRC-8 (SMBus) | `0x07` | `0x00` | False | False | `0x00` | N/A |
| `crc16_modbus` | Modbus RTU CRC-16 (Reflected) | `0x8005` | `0xFFFF` | True | True | `0x0000` | `little` |
| `crc16_ccitt` | CRC-16/CCITT-FALSE (alias of `crc16_ccitt_false`) | `0x1021` | `0xFFFF` | False | False | `0x0000` | `big` |
| `crc16_ccitt_false` | CRC-16/CCITT-FALSE | `0x1021` | `0xFFFF` | False | False | `0x0000` | `big` |
| `crc16_arc` | CRC-16/ARC | `0x8005` | `0x0000` | True | True | `0x0000` | `little` |
| `crc16_dnp` | CRC-16/DNP (DNP3) | `0x3D65` | `0x0000` | True | True | `0xFFFF` | `little` |
| `fletcher16` | Fletcher-16 (two running sums modulo 255, value `sum2 << 8 \| sum1`) | N/A | N/A | No | No | N/A | `little` / `big` |
| `crc32` | Standard IEEE 802.3 CRC-32 | `0x04C11DB7` | `0xFFFFFFFF` | True | True | `0xFFFFFFFF` | `little` |

[[CAPTION:Table]] Supported preset CRC and checksum algorithms.

Names are case-insensitive, and `-` and `_` are interchangeable. These spellings also resolve: `checksum-8`, `checksum8`, `sum-8` (all `sum8`), `xor8` and `xor-8` (`xor`), `crc-16-modbus`, `crc-16-dnp`, `crc-16-arc`, `crc-16-ccitt-false`, `crc-8`, `crc-32` and `fletcher-16`. An unknown algorithm is an error when the protocol is loaded (and therefore in `lint`), not when the first frame is built.

#### 4.1.1 Checksum options
`sum8`, `sum16` and `xor` accept two optional settings under `integrity`: `transform` (`none`, `twos_complement` or `ones_complement`, applied to the final value) and, for `sum8`, `carry_wrap: true` for end-around-carry summation (the LIN enhanced checksum).

#### 4.1.2 Empty input
The CRC of an empty byte string is computed like any other: it follows `init`, reflection and `xorout` (for example `crc16_modbus` of nothing is `0xFFFF`). Checksums (`sum8`, `sum16`, `xor`, `fletcher16`) and `none` are `0`. Having no integrity field is expressed with `algorithm: none`, never as a CRC result.

### 4.2 Custom Parametric CRC (Rocksoft Parameter Model)
Protocols requiring custom or proprietary polynomial algorithms can define the CRC parameters explicitly using the **Rocksoft Model**:

```yaml
framing:
  type: "binary"
  header: [0xAA, 0x55]
  integrity:
    algorithm: "custom"
    width: 16              # Bit width: a multiple of 8, from 8 to 64
    poly: 0x1021           # Generator polynomial (hex or integer)
    init: 0xFFFF           # Initial register value
    refin: false           # Reflect input bytes (true = LSB first)
    refout: false          # Reflect output register before final XOR
    xorout: 0x0000         # Final XOR mask applied to output
    endian: "big"          # Frame byte order: "little" or "big"
    check: 0x29B1          # Optional expected result for ASCII "123456789"
```
[[CAPTION:Figure]] Custom Rocksoft CRC definition in protocol specification.

#### 4.2.1 Parameter Breakdown
- **`width`**: The bit width of the CRC register: a multiple of 8 from 8 to 64.
- **`poly`**: The unreflected polynomial coefficients without the implicit leading high bit (e.g. `0x1021` for \(x^{16} + x^{12} + x^5 + 1\)).
- **`init`**: Initial internal register value prior to processing the first byte.
- **`refin`**: Boolean flag. When `true`, each byte is reflected bit-order (LSB first) prior to feeding into the calculation.
- **`refout`**: Boolean flag. When `true`, the final register state is reflected before the `xorout` stage.
- **`xorout`**: Hexadecimal or integer mask XORed with the final value before transmission.
- **`endian`**: Byte order when serializing the CRC into the frame (`little` or `big`).
- **`check`**: Optional test vector value computed over ASCII `"123456789"` verified when the protocol is loaded: a mismatch is an error.

#### 4.2.2 Validation
A custom model is rejected when `width` is not a multiple of 8 between 8 and 64, when `poly`, `init`, `xorout` or `check` is not an integer that fits in `width` bits, when `poly` is `0`, when `refin` or `refout` is not a boolean, or when `endian` is not `little` or `big`.

#### 4.2.3 Kit protocol mapping
The uart-interface-schema-kit `customParameters` keys `widthBits`, `polynomial`, `initialValue`, `reflectInput`, `reflectOutput` and `finalXor` map to `width`, `poly`, `init`, `refin`, `refout` and `xorout`. Kit `coverage` maps to `covers` (`payload-only` to `payload_only`, `whole-frame-excluding-check` to `full_frame`, `length-to-payload-inclusive` to `after_header`), `finalTransform` (`twosComplement`, `onesComplement`) to `transform`, and `summationMode: carry-wrapped` to `carry_wrap`. `valueEncoding` other than `binary` and `coverageEndMarker` are not supported by the codec and are reported with a warning.

---

## 5. Diagnostic & Stream Dissection Metadata
OmniUART exposes byte-level dissection metadata for visual debugging and stream verification:
- **Frame Slicing**: Every byte in a frame is tagged with its semantic role:
  - `Header` (`0xAA 0x55`)
  - `Length` (`0x06 0x00`)
  - `Command ID` (`0x02`)
  - `Payload` (`0x00 0x1A 0x2B 0x3C`)
  - `Checksum / CRC` (`0x4B 0x8A`)
  - `Footer` (`0x55 0xAA`)
- **CRC Diagnostics**: When a CRC mismatch occurs, OmniUART logs:
  - Computed CRC value vs Received CRC value.
  - The exact byte slice index range evaluated (e.g. `bytes[2:8]`).
  - Bit-by-bit mismatch diff.

---

## 5. Command & Response Model

Commands specify outbound requests dispatched to the device. Each command can define:
- `name`: Unique alphanumeric identifier (e.g. `set_target_temperature`).
- `id`: Opcode / Command identifier (e.g. `0x05`).
- `description`: Human-readable summary.
- `tags`: Free-form labels used to group commands. `dashboard` marks commands shown on the dashboard. Tags are never inferred from the command name.
- `safety`: What the command can do to the device: `read_only` (queries state, changes nothing), `idempotent` (changes state, repeating it has the same effect), `mutating` (changes state, not safe to repeat) or `destructive` (erases, resets or reprograms). **Default: `mutating`**, so a command that does not declare its safety is never run automatically.
- `parameters`: List of typed fields composing the outbound payload.
- `response`: Specification of expected response frame (opcode, timeout, and unpacked fields).
- `correlate`: Names of request parameters that must equal the same-named response fields for a response to be this command's answer (see 5.2). A protocol-level `correlate` list is the default for every command that has all of those names as both a parameter and a response field.

#### 5.2 Response correlation
A response is accepted for a request only if it is a response frame for that command and every `correlate` field in the response equals the value that was sent (use it for a transaction id, sequence number or device address). Any other frame received while waiting (unsolicited telemetry, a late response to an earlier request, a response from another device) does not end the wait and does not fail the exchange: it is collected in `Exchange.unsolicited` and passed to the session's `on_unsolicited` callback. If only such frames arrive the exchange times out with "no matching response". A response frame for a different command with no `correlate` rule is still reported as an invalid response. In code, `DeviceSession(matcher=...)` or `send(..., matcher=...)` replaces the rule with a predicate `(command, request_values, frame) -> bool`. Correlation applies to binary protocols; a delimited text reply is matched by timing only.

#### 5.1 Command safety
- Only `read_only` commands run without a person asking: the dashboard auto-run runs commands that are both tagged `dashboard` and `read_only` (a dashboard command that is not `read_only` is skipped), and auto-poll offers only `read_only` commands that expect a response and whose parameters all have defaults.
- Web and desktop front ends ask for confirmation before sending a `mutating` or `destructive` command (the web API answers `428` until the request carries `"confirm": true`). The CLI refuses a `destructive` command unless `--yes` is given.
- A **read-only session** refuses every command that is not `read_only`, and raw bytes, before anything is written: `send --read-only`, `run --read-only`, the `read_only` field of `POST /api/serial/connect` (`403` on a refused send) and the *Read-only* option in the web and desktop toolbars.
- Earlier versions tagged any command whose name contained `get`, `read`, `info`, `status`, `version`, `poll` or `ping` as `dashboard`, so `set_target_temperature`, `forget_pairing` and `start_sweeping` ran automatically. That heuristic was removed. Add `safety` (and `tags: [dashboard]`) explicitly. Kit protocols carry no safety information, so their commands are `mutating` unless the protocol is edited.

```yaml
commands:
  - name: "set_temperature"
    id: 0x10
    description: "Sets target actuator temperature"
    parameters:
      - name: "channel"
        type: "uint8"
        min: 0
        max: 3
        default: 0
      - name: "target_temp"
        type: "float32"
        endian: "little"
        unit: "°C"
        min: -20.0
        max: 120.0
        default: 25.0
    response:
      id: 0x90
      timeout_ms: 500
      fields:
        - name: "status"
          type: "enum"
          options:
            0: "SUCCESS"
            1: "ERR_OUT_OF_BOUNDS"
            2: "ERR_HARDWARE_FAULT"
        - name: "current_temp"
          type: "float32"
          endian: "little"
          unit: "°C"
```
[[CAPTION:Figure]] Example command specification with typed parameters and response model.

---

## 6. Telemetry & Unsolicited Frames

Telemetry entries represent frames spontaneously transmitted by the device (e.g. periodic sensor broadcasts, alert triggers, or power brownout warnings):

```yaml
telemetry:
  - name: "periodic_environmental_data"
    id: 0x50
    description: "Periodic environmental measurements transmitted every 1000ms"
    fields:
      - name: "humidity_pct"
        type: "uint8"
        unit: "%"
      - name: "pressure_hpa"
        type: "uint16"
        endian: "little"
        unit: "hPa"
      - name: "battery_millivolts"
        type: "uint16"
        endian: "little"
        unit: "mV"
```
[[CAPTION:Figure]] Example telemetry specification.

---

### 6.1 Kit protocol import
When a uart-interface-schema-kit protocol is loaded, its `commands` become commands and its `responses` become telemetry (device-initiated) messages. The kit does not say which request a response answers, so no response is attached to a command. A protocol with no `commands` (NMEA 0183, a COBS sensor stream, the M-Bus long frame) simply has an empty command list; the adapter never invents one. The message id is the constant of the field marked `role: discriminator` (else the first constant field), converted to an integer when it is an integer or a hex or decimal string, otherwise kept as text (an AT command line, an NMEA sentence id). A message without a discriminator constant uses its position as id (commands, with a warning) or its name (responses). Other constant fields remain ordinary fields whose default is the constant. On delimited framing the discriminator is not a parameter, because it is the message text.

## 7. AsyncAPI 2.6.0 Specification Generation & Tooling

OmniUART natively converts all protocol definitions into formal **AsyncAPI 2.6.0 Specification** documents. The `omniuart.core.asyncapi_exporter` module maps serial hardware characteristics and protocol command schemas directly into event-driven AsyncAPI primitives:

### 7.1 Mapping Rules
- **Server Bindings**: Protocol `serial_config` parameters (`baudrate`, `bytesize`, `parity`, `stopbits`, `framing`) map to custom `serial` server protocol bindings (`serial://tty/{baudrate}`).
- **Channels & Operations**:
  - Outbound commands map to AsyncAPI channels `omniuart/cmd/{command_name}` with `publish` operations (Client -> MCU).
  - Inbound responses map to AsyncAPI channels `omniuart/resp/{command_name}` with `subscribe` operations (MCU -> Client).
- **Message Schemas**: Parameter and response field types map to standard JSON Schema primitive types (`integer`, `number`, `string`, `boolean`) retaining range constraints (`minimum`, `maximum`) and unit metadata.

### 7.2 AsyncAPI HTML Compilation via Official Tooling
Documentation builds leverage official `@asyncapi/cli` and `@asyncapi/html-template` npm packages to synthesize interactive HTML documentation pages alongside raw YAML specifications:

```bash
# Generate standalone AsyncAPI HTML viewer using official AsyncAPI CLI
npx @asyncapi/cli generate fromTemplate protocol.asyncapi.yaml @asyncapi/html-template -o ./asyncapi/ --param singleFile=true
```

---

## 8. Schema Catalog & Reference Links

- 📚 **Live Protocol AsyncAPI Catalog**: Explore auto-generated AsyncAPI specifications and interactive HTML documentation for all hardware protocols in the [Hardware Protocol Hub](../protocols/index.md).
- 📄 **Schema AsyncAPI Specification Artifacts**: Download [AsyncAPI 2.6.0 YAML Spec](asyncapi/omniuart-protocol-schema.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/omniuart-protocol-schema.html).
- ⚙️ **Declarative JSON Schema**: Inspect the raw schema definitions in [Protocol JSON Schema](../schemas/protocol.schema.json).

