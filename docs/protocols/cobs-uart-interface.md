# Hardware Protocol Specification: COBS-framed sensor stream

**Version**: `1.0`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `crc16_modbus`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/cobs-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/cobs-uart-interface.html)

## Description
Consistent Overhead Byte Stuffing: the encoding itself guarantees the delimiter byte (0x00) never appears in the encoded data, so -- unlike delimiter-framed -- no escapeByte is needed at all.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `ping` (Command ID: `0x01`)

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: COBS-framed sensor stream
  version: '1.0'
  description: 'Consistent Overhead Byte Stuffing: the encoding itself guarantees
    the delimiter byte (0x00) never appears in the encoded data, so -- unlike delimiter-framed
    -- no escapeByte is needed at all.'
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
        integrity: crc16_modbus
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
