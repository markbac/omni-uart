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

#### `FTP_OpenFileRO` (Command ID: `0x00`) - Opens a file for reading; the ack (FTP_Ack) returns a session id that scopes every subsequent read against this open file.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `seqNumber` | `bytes` | - | - | - |
| `session` | `bytes` | - | - | - |
| `opcode` | `enum` | - | - | `{'4': 'OpenFileRO', '15': 'BurstReadFile', '128': 'Ack', '129': 'Nak'}` |
| `size` | `bytes` | - | - | - |
| `reqOpcode` | `bytes` | - | - | - |
| `burstComplete` | `bytes` | - | - | - |
| `padding` | `bytes` | - | - | - |
| `offset` | `bytes` | - | - | - |
| `path` | `bytes` | - | - | - |

### Category: DASHBOARD

#### `FTP_BurstReadFile` (Command ID: `0x00`) - Requests the server stream the file from offset onward, without individual acks per chunk, until burstComplete is set on the final FTP_Ack.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `seqNumber` | `bytes` | - | - | - |
| `session` | `bytes` | - | - | - |
| `opcode` | `enum` | - | - | `{'4': 'OpenFileRO', '15': 'BurstReadFile', '128': 'Ack', '129': 'Nak'}` |
| `size` | `bytes` | - | - | - |
| `reqOpcode` | `bytes` | - | - | - |
| `burstComplete` | `bytes` | - | - | - |
| `padding` | `bytes` | - | - | - |
| `offset` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: MAVLink FTP
  version: MAVLink v1/v2 FILE_TRANSFER_PROTOCOL (msg 110)
  description: 'File transfer nested inside a normal MAVLink message: every FTP packet,
    of whatever kind, is the SAME outer message type, distinguished only by an inner
    opcode/offset/session sub-header.'
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
        integrity: custom
channels:
  omniuart/cmd/FTP_OpenFileRO:
    publish:
      summary: 'Send command FTP_OpenFileRO (ID: 0x00)'
      description: Opens a file for reading; the ack (FTP_Ack) returns a session id
        that scopes every subsequent read against this open file.
      message:
        name: FTP_OpenFileRO_Message
        title: FTP_OpenFileRO Command
        payload:
          $ref: '#/components/schemas/FTP_OpenFileRO_Request'
  omniuart/cmd/FTP_BurstReadFile:
    publish:
      summary: 'Send command FTP_BurstReadFile (ID: 0x00)'
      description: Requests the server stream the file from offset onward, without
        individual acks per chunk, until burstComplete is set on the final FTP_Ack.
      message:
        name: FTP_BurstReadFile_Message
        title: FTP_BurstReadFile Command
        payload:
          $ref: '#/components/schemas/FTP_BurstReadFile_Request'
components:
  messages: {}
  schemas:
    FTP_OpenFileRO_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for FTP_OpenFileRO
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
        seqNumber:
          type: integer
        session:
          type: integer
        opcode:
          type: integer
        size:
          type: integer
        reqOpcode:
          type: integer
        burstComplete:
          type: integer
        padding:
          type: integer
        offset:
          type: integer
        path:
          type: integer
      description: Opens a file for reading; the ack (FTP_Ack) returns a session id
        that scopes every subsequent read against this open file.
    FTP_BurstReadFile_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for FTP_BurstReadFile
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
        seqNumber:
          type: integer
        session:
          type: integer
        opcode:
          type: integer
        size:
          type: integer
        reqOpcode:
          type: integer
        burstComplete:
          type: integer
        padding:
          type: integer
        offset:
          type: integer
      description: Requests the server stream the file from offset onward, without
        individual acks per chunk, until burstComplete is set on the final FTP_Ack.

```
