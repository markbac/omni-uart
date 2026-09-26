# Hardware Protocol Specification: BinarySensorNode

**Version**: `1.1.0+hw.revB.fw.2.0.1`  
**Author**: IoT Engineering Team  
**Physical Layer**: `115200 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `crc16_modbus`  

## Description
Binary UART protocol for multi-channel environmental sensor node with CRC16-Modbus

## Command Catalog & Message Signatures

### Category: DASHBOARD

#### `ping` (Command ID: `0x01`) - Echo / ping command to check device presence

**Expected Response Payload** (Timeout: `500 ms`):

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `uptime_seconds` | `uint32` | s |

#### `get_readings` (Command ID: `0x02`) - Query latest sensor measurements

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `channel` | `uint8` | - | [0.0, 3.0] | - |

**Expected Response Payload** (Timeout: `1000 ms`):

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `channel` | `uint8` | - |
| `temperature` | `float32` | °C |
| `humidity` | `float32` | % |
| `pressure_hpa` | `float32` | hPa |

### Category: GENERAL

#### `set_sampling_rate` (Command ID: `0x03`) - Configure sensor update frequency

| Parameter | Type | Unit | Range / Constraints | Options |
| :--- | :--- | :--- | :--- | :--- |
| `rate_hz` | `enum` | - | - | `{1: '1 Hz', 5: '5 Hz', 10: '10 Hz', 50: '50 Hz'}` |

**Expected Response Payload** (Timeout: `500 ms`):

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `status` | `uint8` | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: BinarySensorNode
  version: 1.1.0+hw.revB.fw.2.0.1
  description: Binary UART protocol for multi-channel environmental sensor node with
    CRC16-Modbus
  contact:
    name: IoT Engineering Team
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
      description: Echo / ping command to check device presence
      message:
        name: ping_Message
        title: ping Command
        payload:
          $ref: '#/components/schemas/ping_Request'
  omniuart/resp/ping:
    subscribe:
      summary: Receive response for ping
      description: Decoded async payload stream from device after command ping
      message:
        name: ping_Response_Message
        title: ping Response
        payload:
          $ref: '#/components/schemas/ping_Response'
  omniuart/cmd/get_readings:
    publish:
      summary: 'Send command get_readings (ID: 0x02)'
      description: Query latest sensor measurements
      message:
        name: get_readings_Message
        title: get_readings Command
        payload:
          $ref: '#/components/schemas/get_readings_Request'
  omniuart/resp/get_readings:
    subscribe:
      summary: Receive response for get_readings
      description: Decoded async payload stream from device after command get_readings
      message:
        name: get_readings_Response_Message
        title: get_readings Response
        payload:
          $ref: '#/components/schemas/get_readings_Response'
  omniuart/cmd/set_sampling_rate:
    publish:
      summary: 'Send command set_sampling_rate (ID: 0x03)'
      description: Configure sensor update frequency
      message:
        name: set_sampling_rate_Message
        title: set_sampling_rate Command
        payload:
          $ref: '#/components/schemas/set_sampling_rate_Request'
  omniuart/resp/set_sampling_rate:
    subscribe:
      summary: Receive response for set_sampling_rate
      description: Decoded async payload stream from device after command set_sampling_rate
      message:
        name: set_sampling_rate_Response_Message
        title: set_sampling_rate Response
        payload:
          $ref: '#/components/schemas/set_sampling_rate_Response'
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
      description: Echo / ping command to check device presence
    ping_Response:
      type: object
      properties:
        uptime_seconds:
          type: integer
          unit: s
      description: Decoded response frame payload for ping
    get_readings_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 2
          description: Opcode ID for get_readings
        channel:
          type: integer
          minimum: 0.0
          maximum: 3.0
      description: Query latest sensor measurements
    get_readings_Response:
      type: object
      properties:
        channel:
          type: integer
        temperature:
          type: number
          unit: "\xB0C"
        humidity:
          type: number
          unit: '%'
        pressure_hpa:
          type: number
          unit: hPa
      description: Decoded response frame payload for get_readings
    set_sampling_rate_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 3
          description: Opcode ID for set_sampling_rate
        rate_hz:
          type: integer
      description: Configure sensor update frequency
    set_sampling_rate_Response:
      type: object
      properties:
        status:
          type: integer
      description: Decoded response frame payload for set_sampling_rate

```
