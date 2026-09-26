# Hardware Protocol Specification: XMODEM (checksum variant)

**Version**: `classic`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `checksum_8`  

## Description
File transfer over a serial link. Mixes 128/1024-byte framed data blocks (selected by leading byte, not a length field) with completely bare single-byte control codes -- no envelope at all around ACK/NAK/EOT/CAN.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `DataBlock128` (Command ID: `0x01`) - Leading byte 0x01 (SOH) implies a 128-byte data field; nothing else about the length is transmitted.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `header` | `bytes` | - | - | - |
| `blockNumber` | `bytes` | - | - | - |
| `blockNumberComplement` | `bytes` | - | - | - |
| `data` | `bytes` | - | - | - |

#### `DataBlock1024` (Command ID: `0x02`) - Leading byte 0x02 (STX) implies a 1024-byte data field.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `header` | `bytes` | - | - | - |
| `blockNumber` | `bytes` | - | - | - |
| `blockNumberComplement` | `bytes` | - | - | - |
| `data` | `bytes` | - | - | - |

#### `EndOfTransmission` (Command ID: `0x04`) - A single bare byte, 0x04 -- no length field, no checksum, no envelope of any kind.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `controlByte` | `bytes` | - | - | - |

#### `Cancel` (Command ID: `0x18`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `controlByte` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: XMODEM (checksum variant)
  version: classic
  description: File transfer over a serial link. Mixes 128/1024-byte framed data blocks
    (selected by leading byte, not a length field) with completely bare single-byte
    control codes -- no envelope at all around ACK/NAK/EOT/CAN.
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
  omniuart/cmd/DataBlock128:
    publish:
      summary: 'Send command DataBlock128 (ID: 0x01)'
      description: Leading byte 0x01 (SOH) implies a 128-byte data field; nothing
        else about the length is transmitted.
      message:
        name: DataBlock128_Message
        title: DataBlock128 Command
        payload:
          $ref: '#/components/schemas/DataBlock128_Request'
  omniuart/cmd/DataBlock1024:
    publish:
      summary: 'Send command DataBlock1024 (ID: 0x02)'
      description: Leading byte 0x02 (STX) implies a 1024-byte data field.
      message:
        name: DataBlock1024_Message
        title: DataBlock1024 Command
        payload:
          $ref: '#/components/schemas/DataBlock1024_Request'
  omniuart/cmd/EndOfTransmission:
    publish:
      summary: 'Send command EndOfTransmission (ID: 0x04)'
      description: A single bare byte, 0x04 -- no length field, no checksum, no envelope
        of any kind.
      message:
        name: EndOfTransmission_Message
        title: EndOfTransmission Command
        payload:
          $ref: '#/components/schemas/EndOfTransmission_Request'
  omniuart/cmd/Cancel:
    publish:
      summary: 'Send command Cancel (ID: 0x18)'
      description: Dispatch Cancel frame to microcontroller over serial line
      message:
        name: Cancel_Message
        title: Cancel Command
        payload:
          $ref: '#/components/schemas/Cancel_Request'
components:
  messages: {}
  schemas:
    DataBlock128_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for DataBlock128
        header:
          type: integer
        blockNumber:
          type: integer
        blockNumberComplement:
          type: integer
        data:
          type: integer
      description: Leading byte 0x01 (SOH) implies a 128-byte data field; nothing
        else about the length is transmitted.
    DataBlock1024_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 2
          description: Opcode ID for DataBlock1024
        header:
          type: integer
        blockNumber:
          type: integer
        blockNumberComplement:
          type: integer
        data:
          type: integer
      description: Leading byte 0x02 (STX) implies a 1024-byte data field.
    EndOfTransmission_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 4
          description: Opcode ID for EndOfTransmission
        controlByte:
          type: integer
      description: A single bare byte, 0x04 -- no length field, no checksum, no envelope
        of any kind.
    Cancel_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 24
          description: Opcode ID for Cancel
        controlByte:
          type: integer
      description: Command payload for Cancel

```
