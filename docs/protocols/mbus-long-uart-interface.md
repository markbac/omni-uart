# Hardware Protocol Specification: M-Bus (EN 13757-2/3), long/control frame

**Version**: `EN 13757-2`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `checksum_8`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/mbus-long-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/mbus-long-uart-interface.html)

## Description
START L L START C A CI DATA CHECKSUM STOP -- the length is sent twice and the start byte repeats after it, both as on-wire redundancy checks; a STOP byte closes the frame after the checksum too.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `ping` (Command ID: `0x01`)

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: M-Bus (EN 13757-2/3), long/control frame
  version: EN 13757-2
  description: START L L START C A CI DATA CHECKSUM STOP -- the length is sent twice
    and the start byte repeats after it, both as on-wire redundancy checks; a STOP
    byte closes the frame after the checksum too.
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
        parity: even
        stopBits: 1.0
        framingType: binary
        integrity: checksum_8
channels:
  omniuart/cmd/ping:
    publish:
      summary: 'Send command ping (ID: 0x01)'
      description: Dispatch ping frame to microcontroller over serial line
      message:
        name: ping_Message
        title: ping Command
        payload:
          $ref: '#/components/schemas/ping_Request'
components:
  messages: {}
  schemas:
    ping_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for ping
      description: Command payload for ping

```
