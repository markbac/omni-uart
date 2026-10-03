# Hardware Protocol Specification: NMEA 0183

**Version**: `4.11`  
**Physical Layer**: `4800 bps, 8N1.0`  
**Framing**: `delimited`  
**Integrity Algorithm**: `xor`  

> 📄 **AsyncAPI Artifacts**: Download [AsyncAPI 2.6.0 YAML](asyncapi/nmea0183-uart-interface.yaml) | View [Interactive AsyncAPI HTML Docs](asyncapi/nmea0183-uart-interface.html)

## Description
ASCII, delimiter-framed sentence protocol used by GPS/marine navigation equipment. No commands/responses in the request-reply sense -- the device streams sentences unsolicited.

## Command Catalog & Message Signatures

## Device-Initiated Messages

#### `GGA` (Message ID: `GPGGA`) - Global Positioning System Fix Data, e.g. $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47

| Field Name | Type | Unit |
| :--- | :--- | :--- |
| `utcTime` | `string` | - |
| `latitude` | `string` | - |
| `latitudeHemisphere` | `enum` | - |
| `longitude` | `string` | - |
| `longitudeHemisphere` | `enum` | - |
| `fixQuality` | `enum` | - |
| `satellitesUsed` | `string` | - |
| `hdop` | `string` | - |
| `altitude` | `string` | - |
| `altitudeUnits` | `enum` | - |

## Formal AsyncAPI 2.6.0 Specification

```yaml
asyncapi: 2.6.0
info:
  title: NMEA 0183
  version: '4.11'
  description: ASCII, delimiter-framed sentence protocol used by GPS/marine navigation
    equipment. No commands/responses in the request-reply sense -- the device streams
    sentences unsolicited.
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
        framingType: delimited
        integrity: xor
channels: {}
components:
  messages: {}
  schemas: {}

```
