# Hardware Protocol Specification: MAVLink v1

**Version**: `1.0`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `custom`  

## Description
Drone/autopilot telemetry protocol. Header fields (seq/sysid/compid/msgid) sit between the length field and the region LEN actually counts.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `HEARTBEAT` (Command ID: `0x00`) - Message ID 0. seq/sysId/compId/msgId are the 4 precedingHeaderBytes counted separately from LEN, now declared as position=before-length-field fields rather than left as an anonymous count; the fields below them are the LEN-counted payload.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `customMode` | `bytes` | - | - | - |
| `vehicleType` | `bytes` | - | - | - |
| `autopilot` | `bytes` | - | - | - |
| `baseMode` | `bytes` | - | - | - |
| `systemStatus` | `bytes` | - | - | - |
| `mavlinkVersion` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: MAVLink v1
  version: '1.0'
  description: Drone/autopilot telemetry protocol. Header fields (seq/sysid/compid/msgid)
    sit between the length field and the region LEN actually counts.
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
        integrity: custom
channels:
  omniuart/cmd/HEARTBEAT:
    publish:
      summary: 'Send command HEARTBEAT (ID: 0x00)'
      description: Message ID 0. seq/sysId/compId/msgId are the 4 precedingHeaderBytes
        counted separately from LEN, now declared as position=before-length-field
        fields rather than left as an anonymous count; the fields below them are the
        LEN-counted payload.
      message:
        name: HEARTBEAT_Message
        title: HEARTBEAT Command
        payload:
          $ref: '#/components/schemas/HEARTBEAT_Request'
components:
  messages: {}
  schemas:
    HEARTBEAT_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for HEARTBEAT
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
        customMode:
          type: integer
        vehicleType:
          type: integer
        autopilot:
          type: integer
        baseMode:
          type: integer
        systemStatus:
          type: integer
        mavlinkVersion:
          type: integer
      description: Message ID 0. seq/sysId/compId/msgId are the 4 precedingHeaderBytes
        counted separately from LEN, now declared as position=before-length-field
        fields rather than left as an anonymous count; the fields below them are the
        LEN-counted payload.

```
