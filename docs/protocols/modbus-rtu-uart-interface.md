# Hardware Protocol Specification: Modbus RTU

**Version**: `1.0`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `crc16_modbus`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/modbus-rtu-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/modbus-rtu-uart-interface.html)

## Description
Modbus over serial, RTU transmission mode. Frame boundaries are marked by line silence rather than sync bytes or a length field.

## Command Catalog & Message Signatures

### Category: DASHBOARD

#### `ReadHoldingRegistersRequest` (Command ID: `0x03`) - Function 0x03: read a block of holding registers.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'3': 'ReadHoldingRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `startAddress` | `uint16` | - | - | - |
| `quantity` | `uint16` | registers | - | - |

### Category: GENERAL

#### `WriteSingleRegisterRequest` (Command ID: `0x06`) - Function 0x06: write one holding register.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'3': 'ReadHoldingRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `registerAddress` | `uint16` | - | - | - |
| `value` | `uint16` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: Modbus RTU
  version: '1.0'
  description: Modbus over serial, RTU transmission mode. Frame boundaries are marked
    by line silence rather than sync bytes or a length field.
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
        parity: even
        stopBits: 1.0
        framingType: delimited
        integrity: crc16_modbus
channels:
  omniuart/cmd/ReadHoldingRegistersRequest:
    publish:
      summary: 'Send command ReadHoldingRegistersRequest (ID: 0x03)'
      description: 'Function 0x03: read a block of holding registers.'
      message:
        name: ReadHoldingRegistersRequest_Message
        title: ReadHoldingRegistersRequest Command
        payload:
          $ref: '#/components/schemas/ReadHoldingRegistersRequest_Request'
  omniuart/cmd/WriteSingleRegisterRequest:
    publish:
      summary: 'Send command WriteSingleRegisterRequest (ID: 0x06)'
      description: 'Function 0x06: write one holding register.'
      message:
        name: WriteSingleRegisterRequest_Message
        title: WriteSingleRegisterRequest Command
        payload:
          $ref: '#/components/schemas/WriteSingleRegisterRequest_Request'
components:
  messages: {}
  schemas:
    ReadHoldingRegistersRequest_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 3
          description: Opcode ID for ReadHoldingRegistersRequest
        slaveAddress:
          type: integer
        functionCode:
          type: integer
        startAddress:
          type: integer
        quantity:
          type: integer
          unit: registers
      description: 'Function 0x03: read a block of holding registers.'
    WriteSingleRegisterRequest_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 6
          description: Opcode ID for WriteSingleRegisterRequest
        slaveAddress:
          type: integer
        functionCode:
          type: integer
        registerAddress:
          type: integer
        value:
          type: integer
      description: 'Function 0x06: write one holding register.'

```
