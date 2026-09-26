# Hardware Protocol Specification: Serial console (VT100-style CLI), software flow control

**Version**: `illustrative`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `none`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/console-xonxoff-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/console-xonxoff-uart-interface.html)

## Description
Many console/CLI serial ports are wired with only TX/RX/GND -- no RTS/CTS lines exist to carry hardware flow control, so XON/XOFF (software, in-band) is the only option when the far end needs to pace output.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `CommandLine` (Command ID: `0x00`)

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: Serial console (VT100-style CLI), software flow control
  version: illustrative
  description: Many console/CLI serial ports are wired with only TX/RX/GND -- no RTS/CTS
    lines exist to carry hardware flow control, so XON/XOFF (software, in-band) is
    the only option when the far end needs to pace output.
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
        integrity: none
channels:
  omniuart/cmd/CommandLine:
    publish:
      summary: 'Send command CommandLine (ID: 0x00)'
      description: Dispatch CommandLine frame to microcontroller over serial line
      message:
        name: CommandLine_Message
        title: CommandLine Command
        payload:
          $ref: '#/components/schemas/CommandLine_Request'
components:
  messages: {}
  schemas:
    CommandLine_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for CommandLine
        text:
          type: integer
      description: Command payload for CommandLine

```
