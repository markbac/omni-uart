# Hardware Protocol Specification: u-blox UBX

**Version**: `34`  
**Physical Layer**: `4800 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `fletcher16`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/ubx-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/ubx-uart-interface.html)

## Description
GPS/GNSS receiver binary protocol. class+id sit between the sync pattern and the length field -- before the length-counted region, unlike MAVLink's after.

## Command Catalog & Message Signatures

### Category: GNSS/CONFIG

#### `CFG-PRT-Poll` (Command ID: `0x06`) - Poll vs SetBaud share identical class/id, so they don't disambiguate by value at all -- this schema's dispatch algorithm correctly falls back to resolved length instead (0 payload bytes here vs SetBaud's fixed 12), which is genuinely unambiguous, so no role=discriminator is needed on class/id.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |

#### `CFG-PRT-SetBaud` (Command ID: `0x06`) - Same class=0x06, id=0x00 as CFG-PRT-Poll, but with a payload requesting a new port baud rate. The module's own ack is sent at the OLD rate; the host must reconfigure its own UART to the new rate immediately afterwards, per baudRateNegotiation.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |
| `portId` | `uint8` | - | - | - |
| `reserved` | `bytes` | - | - | - |
| `mode` | `uint32` | - | - | - |
| `baudRate` | `uint32` | - | - | - |

### Category: DASHBOARD

#### `CFG-PRT-Poll` (Command ID: `0x06`) - Poll vs SetBaud share identical class/id, so they don't disambiguate by value at all -- this schema's dispatch algorithm correctly falls back to resolved length instead (0 payload bytes here vs SetBaud's fixed 12), which is genuinely unambiguous, so no role=discriminator is needed on class/id.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |

#### `NAV-PVT` (Command ID: `0x01`) - Navigation Position Velocity Time Solution returning fix status, time accuracy, and 3D velocity.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |
| `iTOW` | `uint32` | - | - | - |
| `year` | `uint16` | - | - | - |
| `month` | `uint8` | - | - | - |
| `day` | `uint8` | - | - | - |
| `hour` | `uint8` | - | - | - |
| `min` | `uint8` | - | - | - |
| `sec` | `uint8` | - | - | - |
| `valid` | `uint8` | - | - | - |
| `tAcc` | `uint32` | - | - | - |
| `fixType` | `uint8` | - | - | - |
| `numSV` | `uint8` | - | - | - |
| `gSpeed` | `int32` | - | - | - |
| `heading` | `int32` | - | - | - |

#### `MON-VER` (Command ID: `0x0A`) - Receiver Software and Hardware Version Poll.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |

### Category: GNSS/NAV

#### `NAV-POSLLH` (Command ID: `0x01`) - Geodetic Position Solution returning latitude, longitude, and height above ellipsoid/MSL.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |
| `iTOW` | `uint32` | - | - | - |
| `lon` | `int32` | - | - | - |
| `lat` | `int32` | - | - | - |
| `height` | `int32` | - | - | - |
| `hMSL` | `int32` | - | - | - |
| `hAcc` | `uint32` | - | - | - |
| `vAcc` | `uint32` | - | - | - |

#### `NAV-PVT` (Command ID: `0x01`) - Navigation Position Velocity Time Solution returning fix status, time accuracy, and 3D velocity.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |
| `iTOW` | `uint32` | - | - | - |
| `year` | `uint16` | - | - | - |
| `month` | `uint8` | - | - | - |
| `day` | `uint8` | - | - | - |
| `hour` | `uint8` | - | - | - |
| `min` | `uint8` | - | - | - |
| `sec` | `uint8` | - | - | - |
| `valid` | `uint8` | - | - | - |
| `tAcc` | `uint32` | - | - | - |
| `fixType` | `uint8` | - | - | - |
| `numSV` | `uint8` | - | - | - |
| `gSpeed` | `int32` | - | - | - |
| `heading` | `int32` | - | - | - |

#### `NAV-STATUS` (Command ID: `0x01`) - Receiver Navigation Status Poll.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |

### Category: TELEMETRY

#### `NAV-POSLLH` (Command ID: `0x01`) - Geodetic Position Solution returning latitude, longitude, and height above ellipsoid/MSL.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |
| `iTOW` | `uint32` | - | - | - |
| `lon` | `int32` | - | - | - |
| `lat` | `int32` | - | - | - |
| `height` | `int32` | - | - | - |
| `hMSL` | `int32` | - | - | - |
| `hAcc` | `uint32` | - | - | - |
| `vAcc` | `uint32` | - | - | - |

### Category: GNSS/MON

#### `MON-VER` (Command ID: `0x0A`) - Receiver Software and Hardware Version Poll.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `class` | `uint8` | - | - | - |
| `id` | `uint8` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: u-blox UBX
  version: '34'
  description: GPS/GNSS receiver binary protocol. class+id sit between the sync pattern
    and the length field -- before the length-counted region, unlike MAVLink's after.
  contact:
    name: Mark Bacon
servers:
  serial_link:
    url: serial://tty/4800
    protocol: serial
    description: Physical UART Transport (4800 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 4800
        dataBits: 8
        parity: none
        stopBits: 1.0
        framingType: binary
        integrity: fletcher16
channels:
  omniuart/cmd/CFG-PRT-Poll:
    publish:
      summary: 'Send command CFG-PRT-Poll (ID: 0x06)'
      description: Poll vs SetBaud share identical class/id, so they don't disambiguate
        by value at all -- this schema's dispatch algorithm correctly falls back to
        resolved length instead (0 payload bytes here vs SetBaud's fixed 12), which
        is genuinely unambiguous, so no role=discriminator is needed on class/id.
      message:
        name: CFG-PRT-Poll_Message
        title: CFG-PRT-Poll Command
        payload:
          $ref: '#/components/schemas/CFG-PRT-Poll_Request'
  omniuart/cmd/CFG-PRT-SetBaud:
    publish:
      summary: 'Send command CFG-PRT-SetBaud (ID: 0x06)'
      description: Same class=0x06, id=0x00 as CFG-PRT-Poll, but with a payload requesting
        a new port baud rate. The module's own ack is sent at the OLD rate; the host
        must reconfigure its own UART to the new rate immediately afterwards, per
        baudRateNegotiation.
      message:
        name: CFG-PRT-SetBaud_Message
        title: CFG-PRT-SetBaud Command
        payload:
          $ref: '#/components/schemas/CFG-PRT-SetBaud_Request'
  omniuart/cmd/NAV-POSLLH:
    publish:
      summary: 'Send command NAV-POSLLH (ID: 0x01)'
      description: Geodetic Position Solution returning latitude, longitude, and height
        above ellipsoid/MSL.
      message:
        name: NAV-POSLLH_Message
        title: NAV-POSLLH Command
        payload:
          $ref: '#/components/schemas/NAV-POSLLH_Request'
  omniuart/cmd/NAV-PVT:
    publish:
      summary: 'Send command NAV-PVT (ID: 0x01)'
      description: Navigation Position Velocity Time Solution returning fix status,
        time accuracy, and 3D velocity.
      message:
        name: NAV-PVT_Message
        title: NAV-PVT Command
        payload:
          $ref: '#/components/schemas/NAV-PVT_Request'
  omniuart/cmd/MON-VER:
    publish:
      summary: 'Send command MON-VER (ID: 0x0A)'
      description: Receiver Software and Hardware Version Poll.
      message:
        name: MON-VER_Message
        title: MON-VER Command
        payload:
          $ref: '#/components/schemas/MON-VER_Request'
  omniuart/cmd/NAV-STATUS:
    publish:
      summary: 'Send command NAV-STATUS (ID: 0x01)'
      description: Receiver Navigation Status Poll.
      message:
        name: NAV-STATUS_Message
        title: NAV-STATUS Command
        payload:
          $ref: '#/components/schemas/NAV-STATUS_Request'
components:
  messages: {}
  schemas:
    CFG-PRT-Poll_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 6
          description: Opcode ID for CFG-PRT-Poll
        class:
          type: integer
        id:
          type: integer
      description: Poll vs SetBaud share identical class/id, so they don't disambiguate
        by value at all -- this schema's dispatch algorithm correctly falls back to
        resolved length instead (0 payload bytes here vs SetBaud's fixed 12), which
        is genuinely unambiguous, so no role=discriminator is needed on class/id.
    CFG-PRT-SetBaud_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 6
          description: Opcode ID for CFG-PRT-SetBaud
        class:
          type: integer
        id:
          type: integer
        portId:
          type: integer
        reserved:
          type: integer
        mode:
          type: integer
        baudRate:
          type: integer
      description: Same class=0x06, id=0x00 as CFG-PRT-Poll, but with a payload requesting
        a new port baud rate. The module's own ack is sent at the OLD rate; the host
        must reconfigure its own UART to the new rate immediately afterwards, per
        baudRateNegotiation.
    NAV-POSLLH_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for NAV-POSLLH
        class:
          type: integer
        id:
          type: integer
        iTOW:
          type: integer
        lon:
          type: integer
        lat:
          type: integer
        height:
          type: integer
        hMSL:
          type: integer
        hAcc:
          type: integer
        vAcc:
          type: integer
      description: Geodetic Position Solution returning latitude, longitude, and height
        above ellipsoid/MSL.
    NAV-PVT_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for NAV-PVT
        class:
          type: integer
        id:
          type: integer
        iTOW:
          type: integer
        year:
          type: integer
        month:
          type: integer
        day:
          type: integer
        hour:
          type: integer
        min:
          type: integer
        sec:
          type: integer
        valid:
          type: integer
        tAcc:
          type: integer
        fixType:
          type: integer
        numSV:
          type: integer
        gSpeed:
          type: integer
        heading:
          type: integer
      description: Navigation Position Velocity Time Solution returning fix status,
        time accuracy, and 3D velocity.
    MON-VER_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 10
          description: Opcode ID for MON-VER
        class:
          type: integer
        id:
          type: integer
      description: Receiver Software and Hardware Version Poll.
    NAV-STATUS_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for NAV-STATUS
        class:
          type: integer
        id:
          type: integer
      description: Receiver Navigation Status Poll.

```
