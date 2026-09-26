# Hardware Protocol Specification: SmartActuator

**Version**: `2.0.0`  
**Author**: Motion Control Systems  
**Physical Layer**: `921600 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `crc32`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/smart_actuator.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/smart_actuator.html)

## Description
Servo actuator protocol with CRC32 integrity checking and status reporting

## Command Catalog & Message Signatures

### Category: GENERAL

#### `set_position` (Command ID: `0x1001`) - Sets servo angular position and maximum velocity

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `channel` | `uint8` | - | [0.0, 7.0] | - |
| `angle_degrees` | `float32` | deg | [0.0, 360.0] | - |
| `velocity_limit` | `uint16` | rpm | - | - |

**Expected Response Payload** (Timeout: `200 ms`):

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `channel` | `uint8` | - |
| `current_position` | `float32` | deg |
| `status_flags` | `uint8` | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: SmartActuator
  version: 2.0.0
  description: Servo actuator protocol with CRC32 integrity checking and status reporting
  contact:
    name: Motion Control Systems
servers:
  serial_link:
    url: serial://tty/921600
    protocol: serial
    description: Physical UART Transport (921600 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 921600
        dataBits: 8
        parity: none
        stopBits: 1.0
        framingType: binary
        integrity: crc32
channels:
  omniuart/cmd/set_position:
    publish:
      summary: 'Send command set_position (ID: 0x1001)'
      description: Sets servo angular position and maximum velocity
      message:
        name: set_position_Message
        title: set_position Command
        payload:
          $ref: '#/components/schemas/set_position_Request'
  omniuart/resp/set_position:
    subscribe:
      summary: Receive response for set_position
      description: Decoded async payload stream from device after command set_position
      message:
        name: set_position_Response_Message
        title: set_position Response
        payload:
          $ref: '#/components/schemas/set_position_Response'
components:
  messages: {}
  schemas:
    set_position_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 4097
          description: Opcode ID for set_position
        channel:
          type: integer
          minimum: 0.0
          maximum: 7.0
        angle_degrees:
          type: number
          unit: deg
          minimum: 0.0
          maximum: 360.0
        velocity_limit:
          type: integer
          unit: rpm
      description: Sets servo angular position and maximum velocity
    set_position_Response:
      type: object
      properties:
        channel:
          type: integer
        current_position:
          type: number
          unit: deg
        status_flags:
          type: integer
      description: Decoded response frame payload for set_position

```
