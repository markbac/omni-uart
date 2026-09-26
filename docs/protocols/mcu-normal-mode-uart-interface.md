# Hardware Protocol Specification: Generic MCU normal operation (illustrative)

**Version**: `illustrative`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `checksum_8`  

## Description
Minimal stand-in application-mode protocol, existing only to demonstrate a fully-specified relatedInterfaces transition into the auto-baud bootloader above.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `Ping` (Command ID: `0x01`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `opcode` | `bytes` | - | - | - |
| `reserved` | `bytes` | - | - | - |

#### `EnterBootloader` (Command ID: `0xFF`) - Requests a jump into the ROM bootloader for firmware update. See relatedInterfaces for exactly what happens next.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `opcode` | `bytes` | - | - | - |
| `reserved` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: Generic MCU normal operation (illustrative)
  version: illustrative
  description: Minimal stand-in application-mode protocol, existing only to demonstrate
    a fully-specified relatedInterfaces transition into the auto-baud bootloader above.
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
  omniuart/cmd/Ping:
    publish:
      summary: 'Send command Ping (ID: 0x01)'
      description: Dispatch Ping frame to microcontroller over serial line
      message:
        name: Ping_Message
        title: Ping Command
        payload:
          $ref: '#/components/schemas/Ping_Request'
  omniuart/cmd/EnterBootloader:
    publish:
      summary: 'Send command EnterBootloader (ID: 0xFF)'
      description: Requests a jump into the ROM bootloader for firmware update. See
        relatedInterfaces for exactly what happens next.
      message:
        name: EnterBootloader_Message
        title: EnterBootloader Command
        payload:
          $ref: '#/components/schemas/EnterBootloader_Request'
components:
  messages: {}
  schemas:
    Ping_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for Ping
        opcode:
          type: integer
        reserved:
          type: integer
      description: Command payload for Ping
    EnterBootloader_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 255
          description: Opcode ID for EnterBootloader
        opcode:
          type: integer
        reserved:
          type: integer
      description: Requests a jump into the ROM bootloader for firmware update. See
        relatedInterfaces for exactly what happens next.

```
