# Hardware Protocol Specification: MAVLink v1

**Version**: `1.0`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `custom`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/mavlink-v1-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/mavlink-v1-uart-interface.html)

## Description
Drone/autopilot telemetry protocol. Header fields (seq/sysid/compid/msgid) sit between the length field and the region LEN actually counts.

## Command Catalog & Message Signatures

### Category: TELEMETRY/HEARTBEAT

#### `HEARTBEAT` (Command ID: `0x00`) - Message ID 0. System status heartbeat broadcast by vehicle or ground station.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `customMode` | `uint32` | - | - | - |
| `vehicleType` | `uint8` | - | - | - |
| `autopilot` | `uint8` | - | - | - |
| `baseMode` | `uint8` | - | - | - |
| `systemStatus` | `uint8` | - | - | - |
| `mavlinkVersion` | `uint8` | - | - | - |

### Category: DASHBOARD

#### `HEARTBEAT` (Command ID: `0x00`) - Message ID 0. System status heartbeat broadcast by vehicle or ground station.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `customMode` | `uint32` | - | - | - |
| `vehicleType` | `uint8` | - | - | - |
| `autopilot` | `uint8` | - | - | - |
| `baseMode` | `uint8` | - | - | - |
| `systemStatus` | `uint8` | - | - | - |
| `mavlinkVersion` | `uint8` | - | - | - |

#### `SYS_STATUS` (Command ID: `0x01`) - Message ID 1. System status, battery voltage, current draw, and sensor health.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `onboardSensorsPresent` | `uint32` | - | - | - |
| `onboardSensorsEnabled` | `uint32` | - | - | - |
| `onboardSensorsHealth` | `uint32` | - | - | - |
| `load` | `uint16` | - | - | - |
| `voltageBattery` | `uint16` | - | - | - |
| `currentBattery` | `int16` | - | - | - |
| `batteryRemaining` | `int8` | - | - | - |

### Category: TELEMETRY/STATUS

#### `SYS_STATUS` (Command ID: `0x01`) - Message ID 1. System status, battery voltage, current draw, and sensor health.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `onboardSensorsPresent` | `uint32` | - | - | - |
| `onboardSensorsEnabled` | `uint32` | - | - | - |
| `onboardSensorsHealth` | `uint32` | - | - | - |
| `load` | `uint16` | - | - | - |
| `voltageBattery` | `uint16` | - | - | - |
| `currentBattery` | `int16` | - | - | - |
| `batteryRemaining` | `int8` | - | - | - |

### Category: TELEMETRY/GPS

#### `GPS_RAW_INT` (Command ID: `0x18`) - Message ID 24. Raw GPS location and satellite fix data.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `timeUsec` | `uint64` | - | - | - |
| `fixType` | `uint8` | - | - | - |
| `lat` | `int32` | - | - | - |
| `lon` | `int32` | - | - | - |
| `alt` | `int32` | - | - | - |
| `eph` | `uint16` | - | - | - |
| `epv` | `uint16` | - | - | - |
| `vel` | `uint16` | - | - | - |
| `cog` | `uint16` | - | - | - |
| `satellitesVisible` | `uint8` | - | - | - |

### Category: SENSOR

#### `GPS_RAW_INT` (Command ID: `0x18`) - Message ID 24. Raw GPS location and satellite fix data.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `timeUsec` | `uint64` | - | - | - |
| `fixType` | `uint8` | - | - | - |
| `lat` | `int32` | - | - | - |
| `lon` | `int32` | - | - | - |
| `alt` | `int32` | - | - | - |
| `eph` | `uint16` | - | - | - |
| `epv` | `uint16` | - | - | - |
| `vel` | `uint16` | - | - | - |
| `cog` | `uint16` | - | - | - |
| `satellitesVisible` | `uint8` | - | - | - |

### Category: TELEMETRY/ATTITUDE

#### `ATTITUDE` (Command ID: `0x1E`) - Message ID 30. Vehicle roll, pitch, and yaw angles and angular velocity.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `timeBootMs` | `uint32` | - | - | - |
| `roll` | `float32` | - | - | - |
| `pitch` | `float32` | - | - | - |
| `yaw` | `float32` | - | - | - |
| `rollspeed` | `float32` | - | - | - |
| `pitchspeed` | `float32` | - | - | - |
| `yawspeed` | `float32` | - | - | - |

### Category: COMMAND/ACTION

#### `COMMAND_LONG` (Command ID: `0x4C`) - Message ID 76. Generic command dispatch to vehicle autopilot.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `targetSystem` | `uint8` | - | - | - |
| `targetComponent` | `uint8` | - | - | - |
| `command` | `uint16` | - | - | - |
| `confirmation` | `uint8` | - | - | - |
| `param1` | `float32` | - | - | - |
| `param2` | `float32` | - | - | - |
| `param3` | `float32` | - | - | - |
| `param4` | `float32` | - | - | - |
| `param5` | `float32` | - | - | - |
| `param6` | `float32` | - | - | - |
| `param7` | `float32` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: MAVLink v1
  version: '1.0'
  description: Drone/autopilot telemetry protocol. Header fields (seq/sysid/compid/msgid)
    sit between the length field and the region LEN actually counts.
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
  omniuart/cmd/HEARTBEAT:
    publish:
      summary: 'Send command HEARTBEAT (ID: 0x00)'
      description: Message ID 0. System status heartbeat broadcast by vehicle or ground
        station.
      message:
        name: HEARTBEAT_Message
        title: HEARTBEAT Command
        payload:
          $ref: '#/components/schemas/HEARTBEAT_Request'
  omniuart/cmd/SYS_STATUS:
    publish:
      summary: 'Send command SYS_STATUS (ID: 0x01)'
      description: Message ID 1. System status, battery voltage, current draw, and
        sensor health.
      message:
        name: SYS_STATUS_Message
        title: SYS_STATUS Command
        payload:
          $ref: '#/components/schemas/SYS_STATUS_Request'
  omniuart/cmd/GPS_RAW_INT:
    publish:
      summary: 'Send command GPS_RAW_INT (ID: 0x18)'
      description: Message ID 24. Raw GPS location and satellite fix data.
      message:
        name: GPS_RAW_INT_Message
        title: GPS_RAW_INT Command
        payload:
          $ref: '#/components/schemas/GPS_RAW_INT_Request'
  omniuart/cmd/ATTITUDE:
    publish:
      summary: 'Send command ATTITUDE (ID: 0x1E)'
      description: Message ID 30. Vehicle roll, pitch, and yaw angles and angular
        velocity.
      message:
        name: ATTITUDE_Message
        title: ATTITUDE Command
        payload:
          $ref: '#/components/schemas/ATTITUDE_Request'
  omniuart/cmd/COMMAND_LONG:
    publish:
      summary: 'Send command COMMAND_LONG (ID: 0x4C)'
      description: Message ID 76. Generic command dispatch to vehicle autopilot.
      message:
        name: COMMAND_LONG_Message
        title: COMMAND_LONG Command
        payload:
          $ref: '#/components/schemas/COMMAND_LONG_Request'
components:
  messages: {}
  schemas:
    HEARTBEAT_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 0
          description: Opcode ID for HEARTBEAT
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 0
        customMode:
          type: integer
        vehicleType:
          type: integer
        autopilot:
          type: integer
        baseMode:
          type: integer
        systemStatus:
          type: integer
        mavlinkVersion:
          type: integer
      description: Message ID 0. System status heartbeat broadcast by vehicle or ground
        station.
    SYS_STATUS_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 1
          description: Opcode ID for SYS_STATUS
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 1
        onboardSensorsPresent:
          type: integer
        onboardSensorsEnabled:
          type: integer
        onboardSensorsHealth:
          type: integer
        load:
          type: integer
        voltageBattery:
          type: integer
        currentBattery:
          type: integer
        batteryRemaining:
          type: integer
      description: Message ID 1. System status, battery voltage, current draw, and
        sensor health.
    GPS_RAW_INT_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 24
          description: Opcode ID for GPS_RAW_INT
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 24
        timeUsec:
          type: integer
        fixType:
          type: integer
        lat:
          type: integer
        lon:
          type: integer
        alt:
          type: integer
        eph:
          type: integer
        epv:
          type: integer
        vel:
          type: integer
        cog:
          type: integer
        satellitesVisible:
          type: integer
      description: Message ID 24. Raw GPS location and satellite fix data.
    ATTITUDE_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 30
          description: Opcode ID for ATTITUDE
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 30
        timeBootMs:
          type: integer
        roll:
          type: number
        pitch:
          type: number
        yaw:
          type: number
        rollspeed:
          type: number
        pitchspeed:
          type: number
        yawspeed:
          type: number
      description: Message ID 30. Vehicle roll, pitch, and yaw angles and angular
        velocity.
    COMMAND_LONG_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 76
          description: Opcode ID for COMMAND_LONG
        seq:
          type: integer
        sysId:
          type: integer
        compId:
          type: integer
        msgId:
          type: integer
          default: 76
        targetSystem:
          type: integer
        targetComponent:
          type: integer
        command:
          type: integer
        confirmation:
          type: integer
        param1:
          type: number
        param2:
          type: number
        param3:
          type: number
        param4:
          type: number
        param5:
          type: number
        param6:
          type: number
        param7:
          type: number
      description: Message ID 76. Generic command dispatch to vehicle autopilot.

```
