# Hardware Protocol Specification: PPPoS (PPP over Serial, e.g. to a GSM/cellular modem)

**Version**: `RFC 1662, over a serial modem link`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `crc_16_ccitt_false`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/pppos-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/pppos-uart-interface.html)

## Description
Same async HDLC framing as plain PPP, but hardware flow control isn't optional here: the underlying radio/modem can stall mid-transmission, and without RTS/CTS pacing the host will overrun its buffer.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `Frame` (Command ID: `0x03`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `address` | `bytes` | - | - | - |
| `control` | `bytes` | - | - | - |
| `protocol` | `bytes` | - | - | - |
| `information` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: PPPoS (PPP over Serial, e.g. to a GSM/cellular modem)
  version: RFC 1662, over a serial modem link
  description: 'Same async HDLC framing as plain PPP, but hardware flow control isn''t
    optional here: the underlying radio/modem can stall mid-transmission, and without
    RTS/CTS pacing the host will overrun its buffer.'
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
