# Hardware Protocol Specification: AsciiDevice

**Version**: `1.0.0`  
**Author**: Modem Firmware Team  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `none`  

## Description
Delimited ASCII command protocol (AT-command style)

## Command Catalog & Message Signatures

### Category: GENERAL

#### `TEST` (Command ID: `TEST`) - Check modem connectivity

**Expected Response Payload** (Timeout: `500 ms`):

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `result` | `string` | - |

#### `SET_POWER` (Command ID: `POWER`) - Set output transmission power level

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `dbm` | `int8` | - | [-10.0, 20.0] | - |

**Expected Response Payload** (Timeout: `500 ms`):

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `result` | `string` | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: AsciiDevice
  version: 1.0.0
  description: Delimited ASCII command protocol (AT-command style)
  contact:
    name: Modem Firmware Team
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
  omniuart/cmd/TEST:
    publish:
      summary: 'Send command TEST (ID: TEST)'
      description: Check modem connectivity
      message:
        name: TEST_Message
        title: TEST Command
        payload:
          $ref: '#/components/schemas/TEST_Request'
  omniuart/resp/TEST:
    subscribe:
      summary: Receive response for TEST
      description: Decoded async payload stream from device after command TEST
      message:
        name: TEST_Response_Message
        title: TEST Response
        payload:
          $ref: '#/components/schemas/TEST_Response'
  omniuart/cmd/SET_POWER:
    publish:
      summary: 'Send command SET_POWER (ID: POWER)'
      description: Set output transmission power level
      message:
        name: SET_POWER_Message
        title: SET_POWER Command
        payload:
          $ref: '#/components/schemas/SET_POWER_Request'
  omniuart/resp/SET_POWER:
    subscribe:
      summary: Receive response for SET_POWER
      description: Decoded async payload stream from device after command SET_POWER
      message:
        name: SET_POWER_Response_Message
        title: SET_POWER Response
        payload:
          $ref: '#/components/schemas/SET_POWER_Response'
components:
  messages: {}
  schemas:
    TEST_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: TEST
          description: Opcode ID for TEST
      description: Check modem connectivity
    TEST_Response:
      type: object
      properties:
        result:
          type: integer
      description: Decoded response frame payload for TEST
    SET_POWER_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: POWER
          description: Opcode ID for SET_POWER
        dbm:
          type: integer
          minimum: -10.0
          maximum: 20.0
      description: Set output transmission power level
    SET_POWER_Response:
      type: object
      properties:
        result:
          type: integer
      description: Decoded response frame payload for SET_POWER

```
