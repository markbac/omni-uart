# Hardware Protocol Specification: XBee API Mode

**Version**: `S2C Zigbee firmware`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `checksum_8`  

## Description
Digi XBee radio module binary command protocol, including an AT Command frame setting ATCH (the RF channel/frequency).

## Command Catalog & Message Signatures

### Category: GENERAL

#### `SetChannelATCommand` (Command ID: `CH`) - Frame type 0x08: local AT Command. The AT command here is 'CH' (RF channel/frequency), one of 16 channels in the 2.4GHz band.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `frameType` | `enum` | - | - | `{'8': 'ATCommand', '136': 'ATCommandResponse'}` |
| `frameId` | `bytes` | - | - | - |
| `atCommand` | `bytes` | - | - | - |
| `parameterValue` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: XBee API Mode
  version: S2C Zigbee firmware
  description: Digi XBee radio module binary command protocol, including an AT Command
    frame setting ATCH (the RF channel/frequency).
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
  omniuart/cmd/SetChannelATCommand:
    publish:
      summary: 'Send command SetChannelATCommand (ID: CH)'
      description: 'Frame type 0x08: local AT Command. The AT command here is ''CH''
        (RF channel/frequency), one of 16 channels in the 2.4GHz band.'
      message:
        name: SetChannelATCommand_Message
        title: SetChannelATCommand Command
        payload:
          $ref: '#/components/schemas/SetChannelATCommand_Request'
components:
  messages: {}
  schemas:
    SetChannelATCommand_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: CH
          description: Opcode ID for SetChannelATCommand
        frameType:
          type: integer
        frameId:
          type: integer
        atCommand:
          type: integer
        parameterValue:
          type: integer
      description: 'Frame type 0x08: local AT Command. The AT command here is ''CH''
        (RF channel/frequency), one of 16 channels in the 2.4GHz band.'

```
