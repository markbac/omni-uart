# Hardware Protocol Specification: NMEA 0183

**Version**: `4.11`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `xor8`  

## Description
ASCII, delimiter-framed sentence protocol used by GPS/marine navigation equipment. No commands/responses in the request-reply sense -- the device streams sentences unsolicited.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `ping` (Command ID: `0x01`)

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: NMEA 0183
  version: '4.11'
  description: ASCII, delimiter-framed sentence protocol used by GPS/marine navigation
    equipment. No commands/responses in the request-reply sense -- the device streams
    sentences unsolicited.
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
        framingType: delimited
        integrity: xor8
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
