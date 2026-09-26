# Hardware Protocol Specification: Modbus ASCII

**Version**: `1.0`  
**Physical Layer**: `115200 bps, 7N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `checksum_8`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/modbus-ascii-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/modbus-ascii-uart-interface.html)

## Description
Modbus over serial, ASCII transmission mode. Every logical byte is sent as 2 ASCII hex characters, framed between ':' and CRLF.

## Command Catalog & Message Signatures

### Category: DASHBOARD

#### `ReadHoldingRegistersRequest` (Command ID: `0x03`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `slaveAddress` | `uint8` | - | - | - |
| `functionCode` | `enum` | - | - | `{'3': 'ReadHoldingRegisters'}` |
| `startAddress` | `bytes` | - | - | - |
| `quantity` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: Modbus ASCII
  version: '1.0'
  description: Modbus over serial, ASCII transmission mode. Every logical byte is
    sent as 2 ASCII hex characters, framed between ':' and CRLF.
  contact:
    name: Mark Bacon
servers:
  serial_link:
    url: serial://tty/115200
    protocol: serial
    description: Physical UART Transport (115200 bps, 7N1.0)
    bindings:
      serial:
        baudRate: 115200
        dataBits: 7
        parity: even
        stopBits: 1.0
        framingType: delimited
        integrity: checksum_8
channels:
  omniuart/cmd/ReadHoldingRegistersRequest:
    publish:
      summary: 'Send command ReadHoldingRegistersRequest (ID: 0x03)'
      description: Dispatch ReadHoldingRegistersRequest frame to microcontroller over
        serial line
      message:
        name: ReadHoldingRegistersRequest_Message
        title: ReadHoldingRegistersRequest Command
        payload:
          $ref: '#/components/schemas/ReadHoldingRegistersRequest_Request'
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
      description: Command payload for ReadHoldingRegistersRequest

```
