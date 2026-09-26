# Hardware Protocol Specification: SCPI (Standard Commands for Programmable Instruments) over RS-232

**Version**: `SCPI-99 / IEEE 488.2`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `none`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/scpi-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/scpi-uart-interface.html)

## Description
ASCII line-based instrument control (oscilloscopes, PSUs, DMMs). Baud is configured manually on both sides -- no auto-negotiation -- and commonly must match exactly or the instrument just doesn't respond, with no error reported at all. Chains multiple independent commands onto one physical line via ';', which compoundMessageDelimiter exists specifically for.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `Identify` (Command ID: `*IDN?`) - *IDN?

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `Reset` (Command ID: `*RST`) - *RST

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

#### `MeasureVoltageDC` (Command ID: `MEAS:VOLT:DC?`) - MEAS:VOLT:DC? -- often chained after *RST;*CLS via compoundMessageDelimiter, e.g. one line reading '*RST;*CLS;MEAS:VOLT:DC?'.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

### Category: DASHBOARD

#### `ClearStatus` (Command ID: `*CLS`) - *CLS

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `text` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: SCPI (Standard Commands for Programmable Instruments) over RS-232
  version: SCPI-99 / IEEE 488.2
  description: ASCII line-based instrument control (oscilloscopes, PSUs, DMMs). Baud
    is configured manually on both sides -- no auto-negotiation -- and commonly must
    match exactly or the instrument just doesn't respond, with no error reported at
    all. Chains multiple independent commands onto one physical line via ';', which
    compoundMessageDelimiter exists specifically for.
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
  omniuart/cmd/Identify:
    publish:
      summary: 'Send command Identify (ID: *IDN?)'
      description: '*IDN?'
      message:
        name: Identify_Message
        title: Identify Command
        payload:
          $ref: '#/components/schemas/Identify_Request'
  omniuart/cmd/Reset:
    publish:
      summary: 'Send command Reset (ID: *RST)'
      description: '*RST'
      message:
        name: Reset_Message
        title: Reset Command
        payload:
          $ref: '#/components/schemas/Reset_Request'
  omniuart/cmd/ClearStatus:
    publish:
      summary: 'Send command ClearStatus (ID: *CLS)'
      description: '*CLS'
      message:
        name: ClearStatus_Message
        title: ClearStatus Command
        payload:
          $ref: '#/components/schemas/ClearStatus_Request'
  omniuart/cmd/MeasureVoltageDC:
    publish:
      summary: 'Send command MeasureVoltageDC (ID: MEAS:VOLT:DC?)'
      description: MEAS:VOLT:DC? -- often chained after *RST;*CLS via compoundMessageDelimiter,
        e.g. one line reading '*RST;*CLS;MEAS:VOLT:DC?'.
      message:
        name: MeasureVoltageDC_Message
        title: MeasureVoltageDC Command
        payload:
          $ref: '#/components/schemas/MeasureVoltageDC_Request'
components:
  messages: {}
  schemas:
    Identify_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: '*IDN?'
          description: Opcode ID for Identify
        text:
          type: integer
      description: '*IDN?'
    Reset_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: '*RST'
          description: Opcode ID for Reset
        text:
          type: integer
      description: '*RST'
    ClearStatus_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: '*CLS'
          description: Opcode ID for ClearStatus
        text:
          type: integer
      description: '*CLS'
    MeasureVoltageDC_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: MEAS:VOLT:DC?
          description: Opcode ID for MeasureVoltageDC
        text:
          type: integer
      description: MEAS:VOLT:DC? -- often chained after *RST;*CLS via compoundMessageDelimiter,
        e.g. one line reading '*RST;*CLS;MEAS:VOLT:DC?'.

```
