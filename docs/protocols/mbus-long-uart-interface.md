# Hardware Protocol Specification: M-Bus (EN 13757-2/3), long/control frame

**Version**: `EN 13757-2`  
**Physical Layer**: `300 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `sum8`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/mbus-long-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/mbus-long-uart-interface.html)

## Description
START L L START C A CI DATA CHECKSUM STOP -- the length is sent twice and the start byte repeats after it, both as on-wire redundancy checks; a STOP byte closes the frame after the checksum too.

## Command Catalog & Message Signatures

## Device-Initiated Messages

#### `LongFrame` (Message ID: `LongFrame`)

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `cField` | `uint8` | - |
| `aField` | `uint8` | - |
| `ciField` | `uint8` | - |
| `data` | `bytes` | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: M-Bus (EN 13757-2/3), long/control frame
  version: EN 13757-2
  description: START L L START C A CI DATA CHECKSUM STOP -- the length is sent twice
    and the start byte repeats after it, both as on-wire redundancy checks; a STOP
    byte closes the frame after the checksum too.
servers:
  serial_link:
    url: serial://tty/300
    protocol: serial
    description: Physical UART Transport (300 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 300
        dataBits: 8
        parity: even
        stopBits: 1.0
        framingType: binary
        integrity: sum8
channels:
  omniuart/telemetry/LongFrame:
    subscribe:
      summary: 'Unsolicited telemetry message LongFrame (ID: LongFrame)'
      description: 'Unsolicited telemetry message from device: LongFrame'
      message:
        name: LongFrame_Telemetry_Message
        title: LongFrame Telemetry
        payload:
          $ref: '#/components/schemas/LongFrame_Telemetry'
components:
  messages: {}
  schemas:
    LongFrame_Telemetry:
      type: object
      properties:
        cField:
          type: integer
        aField:
          type: integer
        ciField:
          type: integer
        data:
          type: string
          contentEncoding: base64
      description: Device-initiated telemetry payload for LongFrame

```
