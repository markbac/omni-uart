# Hardware Protocol Specification: PPP (HDLC-like async framing, RFC 1662)

**Version**: `RFC 1662`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `crc_16_ccitt_false`  

## Description
Escapes any occurrence of the flag/escape bytes (and, by default, control chars <0x20) by transmitting escapeByte then (originalByte XOR 0x20) -- a general transform rule, not SLIP's fixed substitute-byte-pair table.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `Frame` (Command ID: `0x03`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `address` | `bytes` | - | - | - |
| `control` | `bytes` | - | - | - |
| `protocol` | `uint16` | - | - | - |
| `information` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: PPP (HDLC-like async framing, RFC 1662)
  version: RFC 1662
  description: Escapes any occurrence of the flag/escape bytes (and, by default, control
    chars <0x20) by transmitting escapeByte then (originalByte XOR 0x20) -- a general
    transform rule, not SLIP's fixed substitute-byte-pair table.
  contact:
    name: Mark Bacon
servers:
  serial_link:
    url: serial://tty/115200
    protocol: serial
    description: Physical UART Transport (115200 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 115200
        dataBits: 8
        parity: none
        stopBits: 1.0
        framingType: delimited
        integrity: crc_16_ccitt_false
channels:
  omniuart/cmd/Frame:
    publish:
      summary: 'Send command Frame (ID: 0x03)'
      description: Dispatch Frame frame to microcontroller over serial line
      message:
        name: Frame_Message
        title: Frame Command
        payload:
          $ref: '#/components/schemas/Frame_Request'
components:
  messages: {}
  schemas:
    Frame_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 3
          description: Opcode ID for Frame
        address:
          type: integer
        control:
          type: integer
        protocol:
          type: integer
        information:
          type: integer
      description: Command payload for Frame

```
