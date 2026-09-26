# Hardware Protocol Specification: LIN Bus (classic checksum)

**Version**: `2.0`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `checksum_8`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/lin-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/lin-uart-interface.html)

## Description
Automotive master/slave bus. Genuinely UART-based (8N1 async bytes) but frame length is looked up by identifier, not sent on the wire.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `WheelSpeedFrame` (Command ID: `0x00`) - One specific LIN identifier; its data length (4 bytes here) is known from the identifier, not transmitted.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `pid` | `bytes` | - | - | - |
| `data` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: LIN Bus (classic checksum)
  version: '2.0'
  description: Automotive master/slave bus. Genuinely UART-based (8N1 async bytes)
    but frame length is looked up by identifier, not sent on the wire.
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
  omniuart/cmd/WheelSpeedFrame:
    publish:
      summary: 'Send command WheelSpeedFrame (ID: 0x00)'
      description: One specific LIN identifier; its data length (4 bytes here) is
        known from the identifier, not transmitted.
      message:
        name: WheelSpeedFrame_Message
        title: WheelSpeedFrame Command
        payload:
          $ref: '#/components/schemas/WheelSpeedFrame_Request'
components:
  messages: {}
  schemas:
    WheelSpeedFrame_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for WheelSpeedFrame
        pid:
          type: integer
        data:
          type: integer
      description: One specific LIN identifier; its data length (4 bytes here) is
        known from the identifier, not transmitted.

```
