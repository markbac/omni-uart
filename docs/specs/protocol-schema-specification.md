# OmniUART Protocol Schema Specification

## 1. Specification Scope
This document formally defines the **OmniUART Protocol Specification Schema** (Version 1.0.0). Protocol definitions can be authored in either YAML or JSON and must conform to the structure documented herein.

The schema governs:
- Protocol metadata and communication parameters.
- Framing rules (binary synchronization preambles, dynamic length fields, integrity algorithms, and footers).
- Payload structure and parameterized command specifications.
- Telemetry and unsolicited notification structures.

---

## 2. Top-Level Schema Structure

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
| `baudrate` | integer | `115200` | Standard baud rates (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600). |
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
| `crc16_ccitt` | X.25 / CCITT-False | `0x1021` | `0xFFFF` | False | False | `0x0000` | `big` |
| `crc32` | Standard IEEE 802.3 CRC-32 | `0x04C11DB7` | `0xFFFFFFFF` | True | True | `0xFFFFFFFF` | `little` |

[[CAPTION:Table]] Supported preset CRC and checksum algorithms.

### 4.2 Custom Parametric CRC (Rocksoft Parameter Model)
Protocols requiring custom or proprietary polynomial algorithms can define the CRC parameters explicitly using the **Rocksoft Model**:

```yaml
framing:
  type: "binary"
  header: [0xAA, 0x55]
  integrity:
    algorithm: "custom"
    width: 16              # Bit width: 8, 16, 24, 32
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
- **`width`**: The bit width of the CRC register (`8`, `16`, `24`, or `32`).
- **`poly`**: The unreflected polynomial coefficients without the implicit leading high bit (e.g. `0x1021` for \(x^{16} + x^{12} + x^5 + 1\)).
- **`init`**: Initial internal register value prior to processing the first byte.
- **`refin`**: Boolean flag. When `true`, each byte is reflected bit-order (LSB first) prior to feeding into the calculation.
- **`refout`**: Boolean flag. When `true`, the final register state is reflected before the `xorout` stage.
- **`xorout`**: Hexadecimal or integer mask XORed with the final value before transmission.
- **`endian`**: Byte order when serializing the CRC into the frame (`little` or `big`).
- **`check`**: Optional test vector value computed over ASCII `"123456789"` used by OmniUART to automatically validate the formula on startup.

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
- `parameters`: List of typed fields composing the outbound payload.
- `response`: Specification of expected response frame (opcode, timeout, and unpacked fields).

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
