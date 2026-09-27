# Hardware Protocol Specification: Modbus RTU

**Version**: `1.0`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `crc16_modbus`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/modbus-rtu-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/modbus-rtu-uart-interface.html)

## Description
Modbus over serial, RTU transmission mode. Frame boundaries are marked by line silence rather than sync bytes or a length field.

## Command Catalog & Message Signatures

### Category: MODBUS/COILS

#### `ReadCoilsRequest` (Command ID: `0x01`) - Function 0x01: Read boolean coils status.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'1': 'ReadCoils', '2': 'ReadDiscreteInputs', '3': 'ReadHoldingRegisters', '4': 'ReadInputRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `startAddress` | `uint16` | - | - | - |
| `quantity` | `uint16` | coils | - | - |

### Category: MODBUS/INPUTS

#### `ReadDiscreteInputsRequest` (Command ID: `0x02`) - Function 0x02: Read discrete inputs status.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'1': 'ReadCoils', '2': 'ReadDiscreteInputs', '3': 'ReadHoldingRegisters', '4': 'ReadInputRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `startAddress` | `uint16` | - | - | - |
| `quantity` | `uint16` | inputs | - | - |

### Category: MODBUS/REGISTERS

#### `ReadHoldingRegistersRequest` (Command ID: `0x03`) - Function 0x03: Read a block of holding registers.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'1': 'ReadCoils', '2': 'ReadDiscreteInputs', '3': 'ReadHoldingRegisters', '4': 'ReadInputRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `startAddress` | `uint16` | - | - | - |
| `quantity` | `uint16` | registers | - | - |

### Category: DASHBOARD

#### `ReadHoldingRegistersRequest` (Command ID: `0x03`) - Function 0x03: Read a block of holding registers.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'1': 'ReadCoils', '2': 'ReadDiscreteInputs', '3': 'ReadHoldingRegisters', '4': 'ReadInputRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `startAddress` | `uint16` | - | - | - |
| `quantity` | `uint16` | registers | - | - |

### Category: MODBUS/INPUT_REGISTERS

#### `ReadInputRegistersRequest` (Command ID: `0x04`) - Function 0x04: Read a block of input registers.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'1': 'ReadCoils', '2': 'ReadDiscreteInputs', '3': 'ReadHoldingRegisters', '4': 'ReadInputRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `startAddress` | `uint16` | - | - | - |
| `quantity` | `uint16` | registers | - | - |

### Category: MODBUS/WRITE

#### `WriteSingleRegisterRequest` (Command ID: `0x06`) - Function 0x06: Write one holding register.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'1': 'ReadCoils', '2': 'ReadDiscreteInputs', '3': 'ReadHoldingRegisters', '4': 'ReadInputRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `registerAddress` | `uint16` | - | - | - |
| `value` | `uint16` | - | - | - |

### Category: MODBUS/WRITE_MULTIPLE

#### `WriteMultipleRegistersRequest` (Command ID: `0x10`) - Function 0x10: Write multiple holding registers.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'1': 'ReadCoils', '2': 'ReadDiscreteInputs', '3': 'ReadHoldingRegisters', '4': 'ReadInputRegisters', '6': 'WriteSingleRegister', '16': 'WriteMultipleRegisters'}` |
| `startAddress` | `uint16` | - | - | - |
| `quantity` | `uint16` | registers | - | - |
| `byteCount` | `uint8` | - | - | - |

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
  omniuart/cmd/ReadCoilsRequest:
    publish:
      summary: 'Send command ReadCoilsRequest (ID: 0x01)'
      description: 'Function 0x01: Read boolean coils status.'
      message:
        name: ReadCoilsRequest_Message
        title: ReadCoilsRequest Command
        payload:
          $ref: '#/components/schemas/ReadCoilsRequest_Request'
  omniuart/cmd/ReadDiscreteInputsRequest:
    publish:
      summary: 'Send command ReadDiscreteInputsRequest (ID: 0x02)'
      description: 'Function 0x02: Read discrete inputs status.'
      message:
        name: ReadDiscreteInputsRequest_Message
        title: ReadDiscreteInputsRequest Command
        payload:
          $ref: '#/components/schemas/ReadDiscreteInputsRequest_Request'
  omniuart/cmd/ReadHoldingRegistersRequest:
    publish:
      summary: 'Send command ReadHoldingRegistersRequest (ID: 0x03)'
      description: 'Function 0x03: Read a block of holding registers.'
      message:
        name: ReadHoldingRegistersRequest_Message
        title: ReadHoldingRegistersRequest Command
        payload:
          $ref: '#/components/schemas/ReadHoldingRegistersRequest_Request'
  omniuart/cmd/ReadInputRegistersRequest:
    publish:
      summary: 'Send command ReadInputRegistersRequest (ID: 0x04)'
      description: 'Function 0x04: Read a block of input registers.'
      message:
        name: ReadInputRegistersRequest_Message
        title: ReadInputRegistersRequest Command
        payload:
          $ref: '#/components/schemas/ReadInputRegistersRequest_Request'
  omniuart/cmd/WriteSingleRegisterRequest:
    publish:
      summary: 'Send command WriteSingleRegisterRequest (ID: 0x06)'
      description: 'Function 0x06: Write one holding register.'
      message:
        name: WriteSingleRegisterRequest_Message
        title: WriteSingleRegisterRequest Command
        payload:
          $ref: '#/components/schemas/WriteSingleRegisterRequest_Request'
  omniuart/cmd/WriteMultipleRegistersRequest:
    publish:
      summary: 'Send command WriteMultipleRegistersRequest (ID: 0x10)'
      description: 'Function 0x10: Write multiple holding registers.'
      message:
        name: WriteMultipleRegistersRequest_Message
        title: WriteMultipleRegistersRequest Command
        payload:
          $ref: '#/components/schemas/WriteMultipleRegistersRequest_Request'
components:
  messages: {}
  schemas:
    ReadCoilsRequest_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for ReadCoilsRequest
        slaveAddress:
          type: integer
        functionCode:
          type: integer
        startAddress:
          type: integer
        quantity:
          type: integer
          unit: coils
      description: 'Function 0x01: Read boolean coils status.'
    ReadDiscreteInputsRequest_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 2
          description: Opcode ID for ReadDiscreteInputsRequest
        slaveAddress:
          type: integer
        functionCode:
          type: integer
        startAddress:
          type: integer
        quantity:
          type: integer
          unit: inputs
      description: 'Function 0x02: Read discrete inputs status.'
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
      description: 'Function 0x03: Read a block of holding registers.'
    ReadInputRegistersRequest_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 4
          description: Opcode ID for ReadInputRegistersRequest
        slaveAddress:
          type: integer
        functionCode:
          type: integer
        startAddress:
          type: integer
        quantity:
          type: integer
          unit: registers
      description: 'Function 0x04: Read a block of input registers.'
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
      description: 'Function 0x06: Write one holding register.'
    WriteMultipleRegistersRequest_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 16
          description: Opcode ID for WriteMultipleRegistersRequest
        slaveAddress:
          type: integer
        functionCode:
          type: integer
        startAddress:
          type: integer
        quantity:
          type: integer
          unit: registers
        byteCount:
          type: integer
      description: 'Function 0x10: Write multiple holding registers.'

```
