# Hardware Protocol Specification: Illustrative Frequency-Hopping Combat Net Radio Control Interface (fictional)

**Version**: `0.1-illustrative`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `crc_16_ccitt_false`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/fh-radio-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/fh-radio-uart-interface.html)

## Description
NOT derived from, or a model of, any specific fielded system's published ICD -- no such document is publicly available. Built only from unclassified, widely-taught operator-level concepts (net ID, hopset/keyset selection by index, time-of-day sync, channel lockout, single-channel fallback) to exercise the schema against this domain without claiming to be real.

## Command Catalog & Message Signatures

### Category: NET-CONTROL

#### `SetNetId` (Command ID: `0x00`) - Selects which hopping net this radio joins. Does not carry key material.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `netId` | `bytes` | - | - | - |

#### `SelectHopset` (Command ID: `0x01`) - Selects a hopset/keyset by index into a locally fill-loaded table -- the index only, never the keyset contents.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `hopsetIndex` | `bytes` | - | - | - |

#### `SetTimeOfDay` (Command ID: `0x02`) - Synchronises the radio's hop-timing clock.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `secondsSinceEpoch` | `bytes` | - | - | - |

### Category: FREQUENCY-MANAGEMENT

#### `SetChannelLockout` (Command ID: `0x03`) - Marks channels as excluded from the hop pattern (e.g. known-interfered channels), analogous in spirit to Bluetooth's AFH channel classification.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `lockoutBitmap` | `bytes` | - | - | - |

#### `SetSingleChannelFrequency` (Command ID: `0x04`) - Fallback non-hopping ('single channel') operating frequency.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `frequencyHz` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: Illustrative Frequency-Hopping Combat Net Radio Control Interface (fictional)
  version: 0.1-illustrative
  description: NOT derived from, or a model of, any specific fielded system's published
    ICD -- no such document is publicly available. Built only from unclassified, widely-taught
    operator-level concepts (net ID, hopset/keyset selection by index, time-of-day
    sync, channel lockout, single-channel fallback) to exercise the schema against
    this domain without claiming to be real.
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
        integrity: crc_16_ccitt_false
channels:
  omniuart/cmd/SetNetId:
    publish:
      summary: 'Send command SetNetId (ID: 0x00)'
      description: Selects which hopping net this radio joins. Does not carry key
        material.
      message:
        name: SetNetId_Message
        title: SetNetId Command
        payload:
          $ref: '#/components/schemas/SetNetId_Request'
  omniuart/cmd/SelectHopset:
    publish:
      summary: 'Send command SelectHopset (ID: 0x01)'
      description: Selects a hopset/keyset by index into a locally fill-loaded table
        -- the index only, never the keyset contents.
      message:
        name: SelectHopset_Message
        title: SelectHopset Command
        payload:
          $ref: '#/components/schemas/SelectHopset_Request'
  omniuart/cmd/SetTimeOfDay:
    publish:
      summary: 'Send command SetTimeOfDay (ID: 0x02)'
      description: Synchronises the radio's hop-timing clock.
      message:
        name: SetTimeOfDay_Message
        title: SetTimeOfDay Command
        payload:
          $ref: '#/components/schemas/SetTimeOfDay_Request'
  omniuart/cmd/SetChannelLockout:
    publish:
      summary: 'Send command SetChannelLockout (ID: 0x03)'
      description: Marks channels as excluded from the hop pattern (e.g. known-interfered
        channels), analogous in spirit to Bluetooth's AFH channel classification.
      message:
        name: SetChannelLockout_Message
        title: SetChannelLockout Command
        payload:
          $ref: '#/components/schemas/SetChannelLockout_Request'
  omniuart/cmd/SetSingleChannelFrequency:
    publish:
      summary: 'Send command SetSingleChannelFrequency (ID: 0x04)'
      description: Fallback non-hopping ('single channel') operating frequency.
      message:
        name: SetSingleChannelFrequency_Message
        title: SetSingleChannelFrequency Command
        payload:
          $ref: '#/components/schemas/SetSingleChannelFrequency_Request'
components:
  messages: {}
  schemas:
    SetNetId_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for SetNetId
        netId:
          type: integer
      description: Selects which hopping net this radio joins. Does not carry key
        material.
    SelectHopset_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for SelectHopset
        hopsetIndex:
          type: integer
      description: Selects a hopset/keyset by index into a locally fill-loaded table
        -- the index only, never the keyset contents.
    SetTimeOfDay_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 2
          description: Opcode ID for SetTimeOfDay
        secondsSinceEpoch:
          type: integer
      description: Synchronises the radio's hop-timing clock.
    SetChannelLockout_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 3
          description: Opcode ID for SetChannelLockout
        lockoutBitmap:
          type: integer
      description: Marks channels as excluded from the hop pattern (e.g. known-interfered
        channels), analogous in spirit to Bluetooth's AFH channel classification.
    SetSingleChannelFrequency_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 4
          description: Opcode ID for SetSingleChannelFrequency
        frequencyHz:
          type: integer
      description: Fallback non-hopping ('single channel') operating frequency.

```
