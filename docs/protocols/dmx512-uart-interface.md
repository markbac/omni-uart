# Hardware Protocol Specification: DMX512

**Version**: `USITT DMX512-A`  
**Physical Layer**: `115200 bps, 8N2.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `none`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/dmx512-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/dmx512-uart-interface.html)

## Description
Unidirectional lighting-control broadcast. Frame boundary is a UART break condition (an extended low period), not a byte value, not silence, and not an identifier lookup -- none of which this schema's framing styles model precisely.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `ChannelFrame` (Command ID: `0x00`) - Start code (0x00 for standard dimmer data) followed by up to 512 channel values; a receiver simply takes however many bytes arrive before the next break.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `startCode` | `bytes` | - | - | - |
| `channelData` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: DMX512
  version: USITT DMX512-A
  description: Unidirectional lighting-control broadcast. Frame boundary is a UART
    break condition (an extended low period), not a byte value, not silence, and not
    an identifier lookup -- none of which this schema's framing styles model precisely.
  contact:
    name: Mark Bacon
servers:
  serial_link:
    url: serial://tty/115200
    protocol: serial
    description: Physical UART Transport (115200 bps, 8N2.0)
    bindings:
      serial:
        baudRate: 115200
        dataBits: 8
        parity: none
        stopBits: 2.0
        framingType: binary
        integrity: none
channels:
  omniuart/cmd/ChannelFrame:
    publish:
      summary: 'Send command ChannelFrame (ID: 0x00)'
      description: Start code (0x00 for standard dimmer data) followed by up to 512
        channel values; a receiver simply takes however many bytes arrive before the
        next break.
      message:
        name: ChannelFrame_Message
        title: ChannelFrame Command
        payload:
          $ref: '#/components/schemas/ChannelFrame_Request'
components:
  messages: {}
  schemas:
    ChannelFrame_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for ChannelFrame
        startCode:
          type: integer
        channelData:
          type: integer
      description: Start code (0x00 for standard dimmer data) followed by up to 512
        channel values; a receiver simply takes however many bytes arrive before the
        next break.

```
