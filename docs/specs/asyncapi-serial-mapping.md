# AsyncAPI Serial Mapping & Interoperability Specification (#226)

## Overview

OmniUART exports native protocol definitions as **AsyncAPI 2.6.0** specification documents (`omniuart generate asyncapi <protocol>`). It also imports an AsyncAPI 2.x or 3.x document with `x-omniuart` extensions as a protocol source (section 5).

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

---

## 5. `x-omniuart` Extensions: AsyncAPI as a Protocol Source (#346)

AsyncAPI describes messages and channels, not the wire format, and has no official binding for UART links. The `x-omniuart` extensions carry everything the native protocol format expresses. A team that already describes its device interfaces in AsyncAPI can use that document as the protocol source instead of keeping a second file. `omniuart generate asyncapi` writes the extensions, so an exported document is itself a usable source.

The vocabulary is defined by [`schemas/x-omniuart.schema.json`](../../schemas/x-omniuart.schema.json), which is generated from the protocol models (`python -m omniuart.schema_export`). It has three parts.

### 5.1 On the document (`$defs/document`)

| Key | Content |
|---|---|
| `version` | Extension vocabulary version, currently `1.0`. |
| `schema_version` | The native `schema_version`. |
| `metadata` | `description` and `author`, when `info` does not carry them exactly. The protocol name and version come from `info.title` and `info.version`. |
| `serial` | The native `serial_config`: `baudrate`, `bytesize`, `parity`, `stopbits`, `flow_control`, `timeout_ms`, RS-485 settings. Without it the `serial` server binding is used, with a warning. |
| `framing` | The native `framing`: header bytes, length field (type, endianness, what it counts), command id field, integrity (algorithm or custom CRC parameters and the bytes it covers), footer, or the delimited prefix, delimiter and suffix. **Required.** |
| `error_replies`, `correlate` and any other protocol-level section | As in the native format. |

### 5.2 On each message (`$defs/message`)

| Key | Content |
|---|---|
| `kind` | `command` (host to device), `response` or `telemetry` (device-initiated). Without it, a message used by a `publish`/`send` operation is a command and one used by `subscribe`/`receive` is telemetry, with a warning. |
| `name` | The command or telemetry name (default: the message `name`). The message `description` becomes the command description. |
| `id` | The message id on the wire. For a response, the response id (default: the command id). Commands that share an id are told apart by leading `fixed` parameters. |
| `safety`, `safety_reason`, `tags`, `correlate` | Command safety (`read_only`, `idempotent`, `mutating`, `destructive`) and the other command attributes. |
| `command`, `timeout_ms`, `success_pattern`, `error_patterns` | Response only: the command it answers, its timeout and the text reply patterns. |

Messages are read from the channels (AsyncAPI 2 `publish`/`subscribe`, AsyncAPI 3 `channels.*.messages` with the `operations` actions) and from `components.messages`, in document order. Local `$ref` pointers are followed; references to other files are reported.

### 5.3 On each payload property (`$defs/field`)

Every native field attribute except `name`: the wire `type`, `endian`, `length`, `length_ref`, `count_ref`, `scale`, `offset_val`, `bit_width`, `offset`, `condition`, `fixed`, `expression`, `encoding` and so on. `options` is a list of `{value, label}` pairs, so integer values stay integers in JSON. Nested fields are JSON Schema `properties` (or `items.properties` for an array), each with its own extension. A property whose extension is `{role: command_id}` is the informative command id written by the exporter and is skipped.

A property without `x-omniuart.type` is accepted only when its JSON Schema type says how it is sent: `boolean` becomes `bool` and `string` becomes `string`, each with a warning. An `integer` or `number` needs a width and endianness, so it is an error. `minimum`, `maximum`, `default`, `x-unit` and `x-scale` fill the matching attributes when the extension does not give them.

### 5.4 Importing

```bash
# Import into the native format (YAML or JSON by the output file's extension)
omniuart import asyncapi device.asyncapi.yaml -o device.yaml
```

A `.yaml` or `.json` file with an `asyncapi` key in a protocol directory is also found by the catalogue and loaded like a native protocol, so every command accepts it directly.

Nothing is dropped silently. Anything that cannot be mapped is an error. Examples are a missing `framing` or message id, an integer property without a wire type, an unknown extension key and a response for an unknown command. The import then fails and lists every error at once. An approximation (a type guessed from JSON Schema, serial settings taken from the server binding, a message kind taken from its operation) is a warning in the import report. Exporting any bundled protocol and importing it again gives an equal protocol; the test suite checks this for every bundled protocol.
