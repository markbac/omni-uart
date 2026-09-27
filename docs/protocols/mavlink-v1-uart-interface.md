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
| `customMode` | `bytes` | - | - | - |
| `vehicleType` | `bytes` | - | - | - |
| `autopilot` | `bytes` | - | - | - |
| `baseMode` | `bytes` | - | - | - |
| `systemStatus` | `bytes` | - | - | - |
| `mavlinkVersion` | `bytes` | - | - | - |

### Category: DASHBOARD

#### `HEARTBEAT` (Command ID: `0x00`) - Message ID 0. System status heartbeat broadcast by vehicle or ground station.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `customMode` | `bytes` | - | - | - |
| `vehicleType` | `bytes` | - | - | - |
| `autopilot` | `bytes` | - | - | - |
| `baseMode` | `bytes` | - | - | - |
| `systemStatus` | `bytes` | - | - | - |
| `mavlinkVersion` | `bytes` | - | - | - |

#### `SYS_STATUS` (Command ID: `0x01`) - Message ID 1. System status, battery voltage, current draw, and sensor health.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `onboardSensorsPresent` | `bytes` | - | - | - |
| `onboardSensorsEnabled` | `bytes` | - | - | - |
| `onboardSensorsHealth` | `bytes` | - | - | - |
| `load` | `bytes` | - | - | - |
| `voltageBattery` | `bytes` | - | - | - |
| `currentBattery` | `bytes` | - | - | - |
| `batteryRemaining` | `bytes` | - | - | - |

### Category: TELEMETRY/STATUS

#### `SYS_STATUS` (Command ID: `0x01`) - Message ID 1. System status, battery voltage, current draw, and sensor health.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `onboardSensorsPresent` | `bytes` | - | - | - |
| `onboardSensorsEnabled` | `bytes` | - | - | - |
| `onboardSensorsHealth` | `bytes` | - | - | - |
| `load` | `bytes` | - | - | - |
| `voltageBattery` | `bytes` | - | - | - |
| `currentBattery` | `bytes` | - | - | - |
| `batteryRemaining` | `bytes` | - | - | - |

### Category: TELEMETRY/GPS

#### `GPS_RAW_INT` (Command ID: `0x18`) - Message ID 24. Raw GPS location and satellite fix data.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `timeUsec` | `bytes` | - | - | - |
| `fixType` | `bytes` | - | - | - |
| `lat` | `bytes` | - | - | - |
| `lon` | `bytes` | - | - | - |
| `alt` | `bytes` | - | - | - |
| `eph` | `bytes` | - | - | - |
| `epv` | `bytes` | - | - | - |
| `vel` | `bytes` | - | - | - |
| `cog` | `bytes` | - | - | - |
| `satellitesVisible` | `bytes` | - | - | - |

### Category: SENSOR

#### `GPS_RAW_INT` (Command ID: `0x18`) - Message ID 24. Raw GPS location and satellite fix data.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `timeUsec` | `bytes` | - | - | - |
| `fixType` | `bytes` | - | - | - |
| `lat` | `bytes` | - | - | - |
| `lon` | `bytes` | - | - | - |
| `alt` | `bytes` | - | - | - |
| `eph` | `bytes` | - | - | - |
| `epv` | `bytes` | - | - | - |
| `vel` | `bytes` | - | - | - |
| `cog` | `bytes` | - | - | - |
| `satellitesVisible` | `bytes` | - | - | - |

### Category: TELEMETRY/ATTITUDE

#### `ATTITUDE` (Command ID: `0x1E`) - Message ID 30. Vehicle roll, pitch, and yaw angles and angular velocity.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `timeBootMs` | `bytes` | - | - | - |
| `roll` | `bytes` | - | - | - |
| `pitch` | `bytes` | - | - | - |
| `yaw` | `bytes` | - | - | - |
| `rollspeed` | `bytes` | - | - | - |
| `pitchspeed` | `bytes` | - | - | - |
| `yawspeed` | `bytes` | - | - | - |

### Category: COMMAND/ACTION

#### `COMMAND_LONG` (Command ID: `0x4C`) - Message ID 76. Generic command dispatch to vehicle autopilot.

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `seq` | `uint8` | - | - | - |
| `sysId` | `uint8` | - | - | - |
| `compId` | `uint8` | - | - | - |
| `msgId` | `uint8` | - | - | - |
| `targetSystem` | `bytes` | - | - | - |
| `targetComponent` | `bytes` | - | - | - |
| `command` | `bytes` | - | - | - |
| `confirmation` | `bytes` | - | - | - |
| `param1` | `bytes` | - | - | - |
| `param2` | `bytes` | - | - | - |
| `param3` | `bytes` | - | - | - |
| `param4` | `bytes` | - | - | - |
| `param5` | `bytes` | - | - | - |
| `param6` | `bytes` | - | - | - |
| `param7` | `bytes` | - | - | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: MAVLink v1
  version: '1.0'
  description: Drone/autopilot telemetry protocol. Header fields (seq/sysid/compid/msgid)
    sit between the length field and the region LEN actually counts.
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
        timeBootMs:
          type: integer
        roll:
          type: integer
        pitch:
          type: integer
        yaw:
          type: integer
        rollspeed:
          type: integer
        pitchspeed:
          type: integer
        yawspeed:
          type: integer
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
        targetSystem:
          type: integer
        targetComponent:
          type: integer
        command:
          type: integer
        confirmation:
          type: integer
        param1:
          type: integer
        param2:
          type: integer
        param3:
          type: integer
        param4:
          type: integer
        param5:
          type: integer
        param6:
          type: integer
        param7:
          type: integer
      description: Message ID 76. Generic command dispatch to vehicle autopilot.

```
