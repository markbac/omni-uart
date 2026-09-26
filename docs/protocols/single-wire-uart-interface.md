# Hardware Protocol Specification: Single-wire half-duplex UART link (illustrative)

**Version**: `illustrative`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `checksum_8`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/single-wire-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/single-wire-uart-interface.html)

## Description
A genuine single shared data line, not just RTS/CTS omitted -- both sides' TX and RX are the same open-drain/tri-state pin, common on microcontroller debug or bootload pins wired for minimal pin count.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `Ping` (Command ID: `0x01`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `opcode` | `bytes` | - | - | - |
| `reserved` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: Single-wire half-duplex UART link (illustrative)
  version: illustrative
  description: A genuine single shared data line, not just RTS/CTS omitted -- both
    sides' TX and RX are the same open-drain/tri-state pin, common on microcontroller
    debug or bootload pins wired for minimal pin count.
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
        framingType: binary
        integrity: checksum_8
channels:
  omniuart/cmd/Ping:
    publish:
      summary: 'Send command Ping (ID: 0x01)'
      description: Dispatch Ping frame to microcontroller over serial line
      message:
        name: Ping_Message
        title: Ping Command
        payload:
          $ref: '#/components/schemas/Ping_Request'
components:
  messages: {}
  schemas:
    Ping_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for Ping
        opcode:
          type: integer
        reserved:
          type: integer
      description: Command payload for Ping

```
