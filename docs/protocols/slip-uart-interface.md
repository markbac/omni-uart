# Hardware Protocol Specification: SLIP (Serial Line Internet Protocol)

**Version**: `RFC 1055`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `none`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/slip-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/slip-uart-interface.html)

## Description
Pure framing protocol -- carries an arbitrary encapsulated packet (typically IP) with no application-level commands or integrity check of its own.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `EncapsulatedPacket` (Command ID: `0x00`) - The opaque packet being carried (e.g. an IP datagram); SLIP does not interpret it.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `data` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: SLIP (Serial Line Internet Protocol)
  version: RFC 1055
  description: Pure framing protocol -- carries an arbitrary encapsulated packet (typically
    IP) with no application-level commands or integrity check of its own.
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
        integrity: none
channels:
  omniuart/cmd/EncapsulatedPacket:
    publish:
      summary: 'Send command EncapsulatedPacket (ID: 0x00)'
      description: The opaque packet being carried (e.g. an IP datagram); SLIP does
        not interpret it.
      message:
        name: EncapsulatedPacket_Message
        title: EncapsulatedPacket Command
        payload:
          $ref: '#/components/schemas/EncapsulatedPacket_Request'
components:
  messages: {}
  schemas:
    EncapsulatedPacket_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for EncapsulatedPacket
        data:
          type: integer
      description: The opaque packet being carried (e.g. an IP datagram); SLIP does
        not interpret it.

```
