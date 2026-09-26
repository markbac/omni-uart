# Hardware Protocol Specification: Generic MCU serial bootloader (illustrative, sync-byte auto-baud)

**Version**: `illustrative`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `checksum_8`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/autobaud-bootloader-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/autobaud-bootloader-uart-interface.html)

## Description
Not modelling any specific vendor's exact protocol -- illustrates the auto-baud mechanism common to several real MCU ROM bootloaders.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `AutoBaudSync` (Command ID: `0x7F`) - The sync byte itself (physicalLayer.autoBaud.syncByte) -- not a normal command, just the timing reference the bootloader measures before anything else can happen.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `syncByte` | `bytes` | - | - | - |

#### `WriteMemory` (Command ID: `0x02`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `opcode` | `bytes` | - | - | - |
| `address` | `bytes` | - | - | - |
| `data` | `bytes` | - | - | - |

#### `Go` (Command ID: `0x03`) - Jumps to application code at the given address, ending the bootloader session.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `opcode` | `bytes` | - | - | - |
| `address` | `bytes` | - | - | - |

### Category: DASHBOARD

#### `GetVersion` (Command ID: `0x01`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `opcode` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: Generic MCU serial bootloader (illustrative, sync-byte auto-baud)
  version: illustrative
  description: Not modelling any specific vendor's exact protocol -- illustrates the
    auto-baud mechanism common to several real MCU ROM bootloaders.
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
        framingType: binary
        integrity: checksum_8
channels:
  omniuart/cmd/AutoBaudSync:
    publish:
      summary: 'Send command AutoBaudSync (ID: 0x7F)'
      description: The sync byte itself (physicalLayer.autoBaud.syncByte) -- not a
        normal command, just the timing reference the bootloader measures before anything
        else can happen.
      message:
        name: AutoBaudSync_Message
        title: AutoBaudSync Command
        payload:
          $ref: '#/components/schemas/AutoBaudSync_Request'
  omniuart/cmd/GetVersion:
    publish:
      summary: 'Send command GetVersion (ID: 0x01)'
      description: Dispatch GetVersion frame to microcontroller over serial line
      message:
        name: GetVersion_Message
        title: GetVersion Command
        payload:
          $ref: '#/components/schemas/GetVersion_Request'
  omniuart/cmd/WriteMemory:
    publish:
      summary: 'Send command WriteMemory (ID: 0x02)'
      description: Dispatch WriteMemory frame to microcontroller over serial line
      message:
        name: WriteMemory_Message
        title: WriteMemory Command
        payload:
          $ref: '#/components/schemas/WriteMemory_Request'
  omniuart/cmd/Go:
    publish:
      summary: 'Send command Go (ID: 0x03)'
      description: Jumps to application code at the given address, ending the bootloader
        session.
      message:
        name: Go_Message
        title: Go Command
        payload:
          $ref: '#/components/schemas/Go_Request'
components:
  messages: {}
  schemas:
    AutoBaudSync_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 127
          description: Opcode ID for AutoBaudSync
        syncByte:
          type: integer
      description: The sync byte itself (physicalLayer.autoBaud.syncByte) -- not a
        normal command, just the timing reference the bootloader measures before anything
        else can happen.
    GetVersion_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for GetVersion
        opcode:
          type: integer
      description: Command payload for GetVersion
    WriteMemory_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 2
          description: Opcode ID for WriteMemory
        opcode:
          type: integer
        address:
          type: integer
        data:
          type: integer
      description: Command payload for WriteMemory
    Go_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 3
          description: Opcode ID for Go
        opcode:
          type: integer
        address:
          type: integer
      description: Jumps to application code at the given address, ending the bootloader
        session.

```
