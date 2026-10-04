# Hardware Protocol Specification: MAVLink FTP

**Version**: `MAVLink v1/v2 FILE_TRANSFER_PROTOCOL (msg 110)`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `custom`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/mavlink-ftp-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/mavlink-ftp-uart-interface.html)

## Description
File transfer nested inside a normal MAVLink message: every FTP packet, of whatever kind, is the SAME outer message type, distinguished only by an inner opcode/offset/session sub-header.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `FTP_OpenFileRO` (Command ID: `0x04`) - Opens a file for reading; the ack (FTP_Ack) returns a session id that scopes every subsequent read against this open file.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `seqNumber` | `uint16` | - | - | - |
| `session` | `uint8` | - | - | - |
| `opcode` | `enum` | - | - | `{'4': 'OpenFileRO', '15': 'BurstReadFile', '128': 'Ack', '129': 'Nak'}` |
| `size` | `uint8` | - | - | - |
| `reqOpcode` | `uint8` | - | - | - |
| `burstComplete` | `uint8` | - | - | - |
| `padding` | `uint8` | - | - | - |
| `offset` | `uint32` | - | - | - |
| `path` | `string` | - | - | - |

#### `FTP_BurstReadFile` (Command ID: `0x0F`) - Requests the server stream the file from offset onward, without individual acks per chunk, until burstComplete is set on the final FTP_Ack.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `seqNumber` | `uint16` | - | - | - |
| `session` | `uint8` | - | - | - |
| `opcode` | `enum` | - | - | `{'4': 'OpenFileRO', '15': 'BurstReadFile', '128': 'Ack', '129': 'Nak'}` |
| `size` | `uint8` | - | - | - |
| `reqOpcode` | `uint8` | - | - | - |
| `burstComplete` | `uint8` | - | - | - |
| `padding` | `uint8` | - | - | - |
| `offset` | `uint32` | - | - | - |

## Device-Initiated Messages

#### `FTP_Ack` (Message ID: `0x80`) - Every burst-read data packet is this same message, distinguished only by offset (where this chunk goes) and burstComplete (whether more are coming) -- there is no separate 'initial'/'follow-on' message name the way G460 or XMODEM have.

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `seq` | `uint8` | - |
| `sysId` | `uint8` | - |
| `compId` | `uint8` | - |
| `msgId` | `uint8` | - |
| `seqNumber` | `uint16` | - |
| `session` | `uint8` | - |
| `opcode` | `enum` | - |
| `size` | `uint8` | - |
| `reqOpcode` | `uint8` | - |
| `burstComplete` | `uint8` | - |
| `padding` | `uint8` | - |
| `offset` | `uint32` | - |
| `data` | `bytes` | - |

#### `FTP_Nak` (Message ID: `0x81`)

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `seq` | `uint8` | - |
| `sysId` | `uint8` | - |
| `compId` | `uint8` | - |
| `msgId` | `uint8` | - |
| `seqNumber` | `uint16` | - |
| `session` | `uint8` | - |
| `opcode` | `enum` | - |
| `size` | `uint8` | - |
| `reqOpcode` | `uint8` | - |
| `burstComplete` | `uint8` | - |
| `padding` | `uint8` | - |
| `offset` | `uint32` | - |
| `errorCode` | `uint8` | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: MAVLink FTP
  version: MAVLink v1/v2 FILE_TRANSFER_PROTOCOL (msg 110)
  description: 'File transfer nested inside a normal MAVLink message: every FTP packet,
    of whatever kind, is the SAME outer message type, distinguished only by an inner
    opcode/offset/session sub-header.'
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
        integrity: custom
channels:
  omniuart/cmd/FTP_OpenFileRO:
    publish:
      summary: 'Send command FTP_OpenFileRO (ID: 0x04)'
      description: Opens a file for reading; the ack (FTP_Ack) returns a session id
        that scopes every subsequent read against this open file.
      message:
        name: FTP_OpenFileRO_Message
        title: FTP_OpenFileRO Command
        payload:
          $ref: '#/components/schemas/FTP_OpenFileRO_Request'
  omniuart/cmd/FTP_BurstReadFile:
    publish:
      summary: 'Send command FTP_BurstReadFile (ID: 0x0F)'
      description: Requests the server stream the file from offset onward, without
        individual acks per chunk, until burstComplete is set on the final FTP_Ack.
      message:
        name: FTP_BurstReadFile_Message
        title: FTP_BurstReadFile Command
        payload:
          $ref: '#/components/schemas/FTP_BurstReadFile_Request'
  omniuart/telemetry/FTP_Ack:
    subscribe:
      summary: 'Unsolicited telemetry message FTP_Ack (ID: 0x80)'
      description: Every burst-read data packet is this same message, distinguished
        only by offset (where this chunk goes) and burstComplete (whether more are
        coming) -- there is no separate 'initial'/'follow-on' message name the way
        G460 or XMODEM have.
      message:
        name: FTP_Ack_Telemetry_Message
        title: FTP_Ack Telemetry
        payload:
          $ref: '#/components/schemas/FTP_Ack_Telemetry'
  omniuart/telemetry/FTP_Nak:
    subscribe:
      summary: 'Unsolicited telemetry message FTP_Nak (ID: 0x81)'
      description: 'Unsolicited telemetry message from device: FTP_Nak'
      message:
        name: FTP_Nak_Telemetry_Message
        title: FTP_Nak Telemetry
        payload:
          $ref: '#/components/schemas/FTP_Nak_Telemetry'
components:
  messages: {}
  schemas:
    FTP_OpenFileRO_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 4
          description: Opcode ID for FTP_OpenFileRO
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 110
        seqNumber:
          type: integer
        session:
          type: integer
          default: 0
        opcode:
          type: string
          enum:
          - '4'
          - '15'
          - '128'
          - '129'
          default: 4
        size:
          type: integer
        reqOpcode:
          type: integer
          default: 0
        burstComplete:
          type: integer
          default: 0
        padding:
          type: integer
          default: 0
        offset:
          type: integer
          default: 0
        path:
          type: string
      description: Opens a file for reading; the ack (FTP_Ack) returns a session id
        that scopes every subsequent read against this open file.
    FTP_BurstReadFile_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 15
          description: Opcode ID for FTP_BurstReadFile
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 110
        seqNumber:
          type: integer
        session:
          type: integer
        opcode:
          type: string
          enum:
          - '4'
          - '15'
          - '128'
          - '129'
          default: 15
        size:
          type: integer
        reqOpcode:
          type: integer
          default: 0
        burstComplete:
          type: integer
          default: 0
        padding:
          type: integer
          default: 0
        offset:
          type: integer
      description: Requests the server stream the file from offset onward, without
        individual acks per chunk, until burstComplete is set on the final FTP_Ack.
    FTP_Ack_Telemetry:
      type: object
      properties:
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 110
        seqNumber:
          type: integer
        session:
          type: integer
        opcode:
          type: string
          enum:
          - '4'
          - '15'
          - '128'
          - '129'
          default: 128
        size:
          type: integer
        reqOpcode:
          type: integer
        burstComplete:
          type: integer
        padding:
          type: integer
          default: 0
        offset:
          type: integer
        data:
          type: string
          contentEncoding: base64
      description: Every burst-read data packet is this same message, distinguished
        only by offset (where this chunk goes) and burstComplete (whether more are
        coming) -- there is no separate 'initial'/'follow-on' message name the way
        G460 or XMODEM have.
    FTP_Nak_Telemetry:
      type: object
      properties:
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 110
        seqNumber:
          type: integer
        session:
          type: integer
        opcode:
          type: string
          enum:
          - '4'
          - '15'
          - '128'
          - '129'
          default: 129
        size:
          type: integer
        reqOpcode:
          type: integer
        burstComplete:
          type: integer
          default: 0
        padding:
          type: integer
          default: 0
        offset:
          type: integer
        errorCode:
          type: integer
      description: Device-initiated telemetry payload for FTP_Nak

```
