# Hardware Protocol Specification: CustomCrcDevice

**Version**: `1.0.0+hw.v2.sha29b1`  
**Author**: Firmware R&D  
**Physical Layer**: `230400 bps, 8N1.0`  
**Framing**: `binary`  
**Integrity Algorithm**: `custom`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/custom_crc_device.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/custom_crc_device.html)

## Description
Proprietary embedded device demonstrating fully custom Rocksoft-modeled CRC-16

## Command Catalog & Message Signatures

### Category: DASHBOARD

#### `get_device_status` (Command ID: `0x10`) - Queries proprietary device operational status

**Expected Response Payload** (Timeout: `300 ms`):

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `system_state` | `enum` | - |
| `cpu_load_pct` | `uint8` | % |
| `supply_voltage_mv` | `uint16` | mV |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: CustomCrcDevice
  version: 1.0.0+hw.v2.sha29b1
  description: Proprietary embedded device demonstrating fully custom Rocksoft-modeled
    CRC-16
  contact:
    name: Firmware R&D
servers:
  serial_link:
    url: serial://tty/230400
    protocol: serial
    description: Physical UART Transport (230400 bps, 8N1.0)
    bindings:
      serial:
        baudRate: 230400
        dataBits: 8
        parity: none
        stopBits: 1.0
        framingType: binary
        integrity: custom
channels:
  omniuart/cmd/get_device_status:
    publish:
      summary: 'Send command get_device_status (ID: 0x10)'
      description: Queries proprietary device operational status
      message:
        name: get_device_status_Message
        title: get_device_status Command
        payload:
          $ref: '#/components/schemas/get_device_status_Request'
  omniuart/resp/get_device_status:
    subscribe:
      summary: Receive response for get_device_status
      description: Decoded async payload stream from device after command get_device_status
      message:
        name: get_device_status_Response_Message
        title: get_device_status Response
        payload:
          $ref: '#/components/schemas/get_device_status_Response'
components:
  messages: {}
  schemas:
    get_device_status_Request:
      type: object
      properties:
        command_id:
          type: integer
          const: 16
          description: Opcode ID for get_device_status
      description: Queries proprietary device operational status
    get_device_status_Response:
      type: object
      properties:
        system_state:
          type: integer
        cpu_load_pct:
          type: integer
          unit: '%'
        supply_voltage_mv:
          type: integer
          unit: mV
      description: Decoded response frame payload for get_device_status

```
