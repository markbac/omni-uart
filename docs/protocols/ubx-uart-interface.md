# Hardware Protocol Specification: u-blox UBX

**Version**: `34`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `fletcher_16`  

## Description
GPS/GNSS receiver binary protocol. class+id sit between the sync pattern and the length field -- before the length-counted region, unlike MAVLink's after.

## Command Catalog & Message Signatures

### Category: DASHBOARD

#### `CFG-PRT-Poll` (Command ID: `0x00`) - Poll vs SetBaud share identical class/id, so they don't disambiguate by value at all -- this schema's dispatch algorithm correctly falls back to resolved length instead (0 payload bytes here vs SetBaud's fixed 12), which is genuinely unambiguous, so no role=discriminator is needed on class/id.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `bytes` | - | - | - |
| `id` | `bytes` | - | - | - |

### Category: GENERAL

#### `CFG-PRT-SetBaud` (Command ID: `0x00`) - Same class=0x06, id=0x00 as CFG-PRT-Poll, but with a payload requesting a new port baud rate. The module's own ack is sent at the OLD rate; the host must reconfigure its own UART to the new rate immediately afterwards, per baudRateNegotiation.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `bytes` | - | - | - |
| `id` | `bytes` | - | - | - |
| `portId` | `bytes` | - | - | - |
| `reserved` | `bytes` | - | - | - |
| `mode` | `bytes` | - | - | - |
| `baudRate` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: u-blox UBX
  version: '34'
  description: GPS/GNSS receiver binary protocol. class+id sit between the sync pattern
    and the length field -- before the length-counted region, unlike MAVLink's after.
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
        parity: none
        stopBits: 1.0
        framingType: binary
        integrity: fletcher_16
channels:
  omniuart/cmd/CFG-PRT-Poll:
    publish:
      summary: 'Send command CFG-PRT-Poll (ID: 0x00)'
      description: Poll vs SetBaud share identical class/id, so they don't disambiguate
        by value at all -- this schema's dispatch algorithm correctly falls back to
        resolved length instead (0 payload bytes here vs SetBaud's fixed 12), which
        is genuinely unambiguous, so no role=discriminator is needed on class/id.
      message:
        name: CFG-PRT-Poll_Message
        title: CFG-PRT-Poll Command
        payload:
          $ref: '#/components/schemas/CFG-PRT-Poll_Request'
  omniuart/cmd/CFG-PRT-SetBaud:
    publish:
      summary: 'Send command CFG-PRT-SetBaud (ID: 0x00)'
      description: Same class=0x06, id=0x00 as CFG-PRT-Poll, but with a payload requesting
        a new port baud rate. The module's own ack is sent at the OLD rate; the host
        must reconfigure its own UART to the new rate immediately afterwards, per
        baudRateNegotiation.
      message:
        name: CFG-PRT-SetBaud_Message
        title: CFG-PRT-SetBaud Command
        payload:
          $ref: '#/components/schemas/CFG-PRT-SetBaud_Request'
components:
  messages: {}
  schemas:
    CFG-PRT-Poll_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for CFG-PRT-Poll
        class:
          type: integer
        id:
          type: integer
      description: Poll vs SetBaud share identical class/id, so they don't disambiguate
        by value at all -- this schema's dispatch algorithm correctly falls back to
        resolved length instead (0 payload bytes here vs SetBaud's fixed 12), which
        is genuinely unambiguous, so no role=discriminator is needed on class/id.
    CFG-PRT-SetBaud_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for CFG-PRT-SetBaud
        class:
          type: integer
        id:
          type: integer
        portId:
          type: integer
        reserved:
          type: integer
        mode:
          type: integer
        baudRate:
          type: integer
      description: Same class=0x06, id=0x00 as CFG-PRT-Poll, but with a payload requesting
        a new port baud rate. The module's own ack is sent at the OLD rate; the host
        must reconfigure its own UART to the new rate immediately afterwards, per
        baudRateNegotiation.

```
