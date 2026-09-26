# Hardware Protocol Specification: M-Bus (EN 13757-2/3), short frame

**Version**: `EN 13757-2`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `checksum_8`  

## Description
Utility meter readout bus. 8E1 -- even parity, a format neither G460 nor any earlier test used -- at one of several fixed baud rates the spec enumerates (300/600/1200/2400/4800/9600).

## Command Catalog & Message Signatures

### Category: GENERAL

#### `ShortFrame` (Command ID: `0x00`) - The whole frame is fixed at 5 bytes; there is no length field to describe.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `cField` | `uint8` | - | - | - |
| `aField` | `uint8` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: M-Bus (EN 13757-2/3), short frame
  version: EN 13757-2
  description: Utility meter readout bus. 8E1 -- even parity, a format neither G460
    nor any earlier test used -- at one of several fixed baud rates the spec enumerates
    (300/600/1200/2400/4800/9600).
  contact:
    name: Mark Bacon
servers:
  serial_link:
    url: serial://tty/9600
    protocol: serial
    description: Physical UART Transport (9600 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 9600
        dataBits: 8
        parity: even
        stopBits: 1.0
        framingType: delimited
        integrity: checksum_8
channels:
  omniuart/cmd/ShortFrame:
    publish:
      summary: 'Send command ShortFrame (ID: 0x00)'
      description: The whole frame is fixed at 5 bytes; there is no length field to
        describe.
      message:
        name: ShortFrame_Message
        title: ShortFrame Command
        payload:
          $ref: '#/components/schemas/ShortFrame_Request'
components:
  messages: {}
  schemas:
    ShortFrame_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for ShortFrame
        cField:
          type: integer
        aField:
          type: integer
      description: The whole frame is fixed at 5 bytes; there is no length field to
        describe.

```
