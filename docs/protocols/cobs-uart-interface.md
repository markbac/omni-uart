# Hardware Protocol Specification: COBS-framed sensor stream

**Version**: `1.0`  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `crc16_modbus`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/cobs-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/cobs-uart-interface.html)

## Description
Consistent Overhead Byte Stuffing: the encoding itself guarantees the delimiter byte (0x00) never appears in the encoded data, so -- unlike delimiter-framed -- no escapeByte is needed at all.

## Command Catalog & Message Signatures

## Device-Initiated Messages

#### `SensorReading` (Message ID: `SensorReading`)

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `sensorId` | `uint8` | - |
| `value` | `float32` | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: COBS-framed sensor stream
  version: '1.0'
  description: 'Consistent Overhead Byte Stuffing: the encoding itself guarantees
    the delimiter byte (0x00) never appears in the encoded data, so -- unlike delimiter-framed
    -- no escapeByte is needed at all.'
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
  omniuart/telemetry/SensorReading:
    subscribe:
      summary: 'Unsolicited telemetry message SensorReading (ID: SensorReading)'
      description: 'Unsolicited telemetry message from device: SensorReading'
      message:
        name: SensorReading_Telemetry_Message
        title: SensorReading Telemetry
        payload:
          $ref: '#/components/schemas/SensorReading_Telemetry'
components:
  messages: {}
  schemas:
    SensorReading_Telemetry:
      type: object
      properties:
        sensorId:
          type: integer
        value:
          type: number
      description: Device-initiated telemetry payload for SensorReading

```
