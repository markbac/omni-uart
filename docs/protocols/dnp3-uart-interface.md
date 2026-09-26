# Hardware Protocol Specification: DNP3 (Distributed Network Protocol), serial data link layer

**Version**: `DNP3-2013`  
**Physical Layer**: `9600 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `crc_16_dnp`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/dnp3-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/dnp3-uart-interface.html)

## Description
SCADA/utility protocol. Its data-link CRC is exactly this schema's existing crc-16-dnp preset -- unused since it was first added several rounds ago. Its real structural novelty: data is chunked into 16-byte blocks, EACH with its own trailing CRC, not one check for the whole frame.

## Command Catalog & Message Signatures

### Category: GENERAL

#### `DataLinkFrame` (Command ID: `0x00`) - control/destination/source are the LENGTH-counted header; userData is the application payload. userData is actually split into 16-byte blocks, each followed by its OWN separate CRC-16/DNP (the final block may be shorter) -- now recorded via framing.dataBlockChecking, though variableLength:remainder here still computes userData's byte count by simple subtraction against the frame's declared length, which INCLUDES the interleaved per-block check bytes; the true logical (non-check) data length is smaller and only recoverable by actually walking the blocks, not by this schema's arithmetic alone -- see dataBlockChecking's own description.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `control` | `bytes` | - | - | - |
| `destination` | `bytes` | - | - | - |
| `source` | `bytes` | - | - | - |
| `userData` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: DNP3 (Distributed Network Protocol), serial data link layer
  version: DNP3-2013
  description: 'SCADA/utility protocol. Its data-link CRC is exactly this schema''s
    existing crc-16-dnp preset -- unused since it was first added several rounds ago.
    Its real structural novelty: data is chunked into 16-byte blocks, EACH with its
    own trailing CRC, not one check for the whole frame.'
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
        framingType: binary
        integrity: crc_16_dnp
channels:
  omniuart/cmd/DataLinkFrame:
    publish:
      summary: 'Send command DataLinkFrame (ID: 0x00)'
      description: control/destination/source are the LENGTH-counted header; userData
        is the application payload. userData is actually split into 16-byte blocks,
        each followed by its OWN separate CRC-16/DNP (the final block may be shorter)
        -- now recorded via framing.dataBlockChecking, though variableLength:remainder
        here still computes userData's byte count by simple subtraction against the
        frame's declared length, which INCLUDES the interleaved per-block check bytes;
        the true logical (non-check) data length is smaller and only recoverable by
        actually walking the blocks, not by this schema's arithmetic alone -- see
        dataBlockChecking's own description.
      message:
        name: DataLinkFrame_Message
        title: DataLinkFrame Command
        payload:
          $ref: '#/components/schemas/DataLinkFrame_Request'
components:
  messages: {}
  schemas:
    DataLinkFrame_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for DataLinkFrame
        control:
          type: integer
        destination:
          type: integer
        source:
          type: integer
        userData:
          type: integer
      description: control/destination/source are the LENGTH-counted header; userData
        is the application payload. userData is actually split into 16-byte blocks,
        each followed by its OWN separate CRC-16/DNP (the final block may be shorter)
        -- now recorded via framing.dataBlockChecking, though variableLength:remainder
        here still computes userData's byte count by simple subtraction against the
        frame's declared length, which INCLUDES the interleaved per-block check bytes;
        the true logical (non-check) data length is smaller and only recoverable by
        actually walking the blocks, not by this schema's arithmetic alone -- see
        dataBlockChecking's own description.

```
