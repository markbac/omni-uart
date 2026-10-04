# AsyncAPI Serial Mapping & Interoperability Specification (#226)

## Overview

OmniUART provides built-in export capability to convert native protocol definitions into **AsyncAPI 2.6.0** specification documents (`omniuart generate asyncapi <protocol>`).

This document describes how OmniUART maps binary/ASCII serial UART protocol structures into AsyncAPI channels, server bindings, and payload schemas, distinguishing standard AsyncAPI constructs from OmniUART extensions.

---

## 1. Transport & Server Binding Representation

Serial UART is represented as a custom server protocol binding under `servers.serial_link`.

```yaml
servers:
  serial_link:
    url: serial://tty/115200
    protocol: serial
    description: Physical UART Transport (115200 bps, 8N1)
    bindings:
      serial:
        baudRate: 115200
        dataBits: 8
        parity: "none"
        stopBits: 1
        framingType: binary
        integrity: crc16_modbus
```

### Server Binding Attributes
- **`baudRate`** *(integer)*: Serial communication baud rate (e.g., 9600, 115200).
- **`dataBits`** *(integer)*: Bit count per frame character (5–9).
- **`parity`** *(string)*: Parity checking (`none`, `even`, `odd`, `mark`, `space`).
- **`stopBits`** *(number)*: Stop bit configuration (1, 1.5, 2).
- **`framingType`** *(string)*: Protocol framing mode (`binary` or `ascii`).
- **`integrity`** *(string)*: CRC or checksum algorithm identifier (`crc16_modbus`, `crc32`, `checksum8`, `none`).

---

## 2. Channel & Operation Mapping

OmniUART maps command/response exchanges and spontaneous telemetry to logical AsyncAPI channels.

| Protocol Construct | Channel URI Format | Operation | Direction | Description |
|---|---|---|---|---|
| **Command** | `omniuart/cmd/{command_name}` | `publish` | Client $\rightarrow$ Device | Transmit command frame over UART |
| **Response** | `omniuart/resp/{command_name}` | `subscribe` | Device $\rightarrow$ Client | Receive response frame from UART |
| **Telemetry** | `omniuart/telemetry/{telemetry_name}` | `subscribe` | Device $\rightarrow$ Client | Unsolicited periodic telemetry broadcast |

---

## 3. Data Schema Mapping

OmniUART field specs map to JSON Schema / AsyncAPI property definitions:

| OmniUART Field Type | AsyncAPI JSON Schema Type | Format / Encoding Attributes |
|---|---|---|
| `uint8`, `int8`, `uint16`, `int16`, `uint32`, `int32`, `uint64`, `int64` | `integer` | `minimum`, `maximum`, `default` |
| `float32`, `float64` | `number` | `multipleOf` (if scale set) |
| `bool`, `boolean` | `boolean` | - |
| `string`, `str`, `ascii` | `string` | - |
| `bytes`, `raw`, `hex` | `string` | `contentEncoding: base64` |
| `enum` | `string` | `enum: [key1, key2, ...]` |

---

## 4. Interoperability Limits & Consumer Guidance

1. **Custom Serial Binding**: The `bindings.serial` object is an OmniUART-specific extension to AsyncAPI 2.6.0 server bindings. Standard AsyncAPI parsers will ignore unknown server bindings without throwing errors.
2. **Binary Bitfields & Scaling**: Binary bitfield offsets and raw integer scaling (`scale`, `offset_val`) are annotated via extended schema properties (`unit`, `multipleOf`) but require an OmniUART-compatible codec runtime for full binary bit-level serialization/deserialization.
3. **Correlation**: Request-response correlation on physical UART relies on `command_id` opcode matching on the wire.
