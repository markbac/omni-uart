# Hardware Protocol Specification: XBee API Mode

**Version**: `S2C Zigbee firmware`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `sum8`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/xbee-api-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/xbee-api-uart-interface.html)

## Description
Digi XBee radio module binary command protocol, including an AT Command frame setting ATCH (the RF channel/frequency).

## Command Catalog & Message Signatures

### Category: XBEE/AT_COMMAND

#### `SetChannelATCommand` (Command ID: `0x08`) - Frame type 0x08: local AT Command. The AT command here is 'CH' (RF channel/frequency), one of 16 channels in the 2.4GHz band.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `frameId` | `uint8` | - | - | - |
| `atCommand` | `string` | - | - | - |
| `parameterValue` | `uint8` | - | - | - |

### Category: DASHBOARD

#### `SetChannelATCommand` (Command ID: `0x08`) - Frame type 0x08: local AT Command. The AT command here is 'CH' (RF channel/frequency), one of 16 channels in the 2.4GHz band.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `frameId` | `uint8` | - | - | - |
| `atCommand` | `string` | - | - | - |
| `parameterValue` | `uint8` | - | - | - |

### Category: XBEE/TRANSMIT

#### `TransmitRequest` (Command ID: `0x10`) - Frame type 0x10: Transmit data packet to 64-bit destination address.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `frameId` | `uint8` | - | - | - |
| `dest64` | `bytes` | - | - | - |
| `dest16` | `uint16` | - | - | - |
| `broadcastRadius` | `uint8` | - | - | - |
| `options` | `uint8` | - | - | - |
| `payload` | `bytes` | - | - | - |

### Category: XBEE/REMOTE_AT

#### `RemoteATCommand` (Command ID: `0x17`) - Frame type 0x17: Issue AT Command to remote node in mesh network.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `frameId` | `uint8` | - | - | - |
| `dest64` | `bytes` | - | - | - |
| `dest16` | `uint16` | - | - | - |
| `applyOptions` | `uint8` | - | - | - |
| `atCommand` | `string` | - | - | - |

## Device-Initiated Messages

#### `ATCommandResponse` (Message ID: `0x88`)

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `frameId` | `uint8` | - |
| `atCommand` | `string` | - |
| `commandStatus` | `uint8` | - |

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
        integrity: sum8
channels:
  omniuart/cmd/SetChannelATCommand:
    publish:
      summary: 'Send command SetChannelATCommand (ID: 0x08)'
      description: 'Frame type 0x08: local AT Command. The AT command here is ''CH''
        (RF channel/frequency), one of 16 channels in the 2.4GHz band.'
      message:
        name: SetChannelATCommand_Message
        title: SetChannelATCommand Command
        payload:
          $ref: '#/components/schemas/SetChannelATCommand_Request'
  omniuart/cmd/TransmitRequest:
    publish:
      summary: 'Send command TransmitRequest (ID: 0x10)'
      description: 'Frame type 0x10: Transmit data packet to 64-bit destination address.'
      message:
        name: TransmitRequest_Message
        title: TransmitRequest Command
        payload:
          $ref: '#/components/schemas/TransmitRequest_Request'
  omniuart/cmd/RemoteATCommand:
    publish:
      summary: 'Send command RemoteATCommand (ID: 0x17)'
      description: 'Frame type 0x17: Issue AT Command to remote node in mesh network.'
      message:
        name: RemoteATCommand_Message
        title: RemoteATCommand Command
        payload:
          $ref: '#/components/schemas/RemoteATCommand_Request'
components:
  messages: {}
  schemas:
    SetChannelATCommand_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 8
          description: Opcode ID for SetChannelATCommand
        frameId:
          type: integer
        atCommand:
          type: integer
        parameterValue:
          type: integer
      description: 'Frame type 0x08: local AT Command. The AT command here is ''CH''
        (RF channel/frequency), one of 16 channels in the 2.4GHz band.'
    TransmitRequest_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 16
          description: Opcode ID for TransmitRequest
        frameId:
          type: integer
        dest64:
          type: integer
        dest16:
          type: integer
        broadcastRadius:
          type: integer
        options:
          type: integer
        payload:
          type: integer
      description: 'Frame type 0x10: Transmit data packet to 64-bit destination address.'
    RemoteATCommand_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 23
          description: Opcode ID for RemoteATCommand
        frameId:
          type: integer
        dest64:
          type: integer
        dest16:
          type: integer
        applyOptions:
          type: integer
        atCommand:
          type: integer
      description: 'Frame type 0x17: Issue AT Command to remote node in mesh network.'

```
