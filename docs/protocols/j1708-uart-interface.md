# Hardware Protocol Specification: SAE J1708

**Version**: `J1708`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `checksum_8`  

## Description
Heavy-vehicle diagnostic multi-drop bus. Fixed 9600 8N1 -- no parity at all, unlike M-Bus's 8E1 or G460's default -- a third distinct combination across the protocols tried so far.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `Message` (Command ID: `0x00`) - MID implies the message's format/length via an external lookup, much like LIN's identifier -- though here the boundary itself comes from bus silence, not a table (Message/data here has whatever length the specific MID's fields sum to).

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `mid` | `uint8` | - | - | - |
| `data` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: SAE J1708
  version: J1708
  description: Heavy-vehicle diagnostic multi-drop bus. Fixed 9600 8N1 -- no parity
    at all, unlike M-Bus's 8E1 or G460's default -- a third distinct combination across
    the protocols tried so far.
  contact:
    name: Mark Bacon
servers:
  serial_link:
    url: serial://tty/9600
    protocol: serial
    description: Physical UART Transport (9600 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 9600
        dataBits: 8
        parity: none
        stopBits: 1.0
        framingType: delimited
        integrity: checksum_8
channels:
  omniuart/cmd/Message:
    publish:
      summary: 'Send command Message (ID: 0x00)'
      description: MID implies the message's format/length via an external lookup,
        much like LIN's identifier -- though here the boundary itself comes from bus
        silence, not a table (Message/data here has whatever length the specific MID's
        fields sum to).
      message:
        name: Message_Message
        title: Message Command
        payload:
          $ref: '#/components/schemas/Message_Request'
components:
  messages: {}
  schemas:
    Message_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for Message
        mid:
          type: integer
        data:
          type: integer
      description: MID implies the message's format/length via an external lookup,
        much like LIN's identifier -- though here the boundary itself comes from bus
        silence, not a table (Message/data here has whatever length the specific MID's
        fields sum to).

```
