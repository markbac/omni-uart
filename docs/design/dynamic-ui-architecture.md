# OmniUART Dynamic Web UI Architecture

## 1. Design Overview
The OmniUART Web UI provides an interactive, schema-driven dashboard that eliminates the need for hardcoded GUI applications for custom UART protocols.

Key characteristics:
- **Zero Frontend Build Dependencies**: Built using modern vanilla ES modules, native Web Components, and modern CSS variables. Running `omni-uart ui` requires no `npm`, `node`, or frontend bundling.
- **Dynamic Form Generation**: The UI reads the protocol schema over a REST endpoint (`/api/protocol`) and automatically synthesizes input widgets tailored to each command's parameters.
- **High-Performance Streaming**: A bidirectional WebSocket (`/ws/serial`) streams raw byte hex dumps and decoded telemetry frames directly to the client at 60 FPS without DOM thrashing.
- **Virtual Device Toggle**: Includes a one-click switch between physical hardware serial ports and the virtual MCU loopback simulator.

---

## 2. Dynamic Form Generation Logic

When a protocol is loaded, the client inspects each command's parameter list and maps types to UI controls:

| Parameter Type | Schema Attributes | Rendered UI Control | Interaction Behavior |
| :--- | :--- | :--- | :--- |
| `uint8`, `int16`, `float32` | `min`, `max`, `step`, `unit` | HTML5 `<input type="number">` or Slider | Bounds validation; units appended in label. |
| `enum` | `options: {0: "OFF", 1: "ON"}` | HTML5 `<select>` dropdown | Displays human-readable label; sends numeric code. |
| `bool` | `default: false` | Toggle switch | Transmits `0` or `1`. |
| `string` | `max_length`, `encoding` | Text box with character counter | Live length enforcement. |
| `bytes` | `length` | Hex-formatted text field (`0x..`) | Auto-formats pairs of hex characters. |

[[CAPTION:Table]] Schema-to-UI control mapping.

---

## 3. UI Component Layout

The interface is structured into four primary viewports:

```
+---------------------------------------------------------------------------------+
|  OmniUART [Protocol: SensorNode v1.2]   [Port: COM4 v] [Baud: 115200 v] [CONNECT] |
|  [x] Virtual Loopback Mode    [Traffic: TX 142pkts / RX 140pkts]   [Status: ACTIVE] |
+---------------------------------------------------------------------------------+
|  COMMAND DISPATCH (Dynamic)             |  REAL-TIME PACKET INSPECTOR             |
|                                         |  [All] [TX Only] [RX Only] [Clear Log]  |
|  Command: [set_threshold          v]    |                                         |
|  +-----------------------------------+  |  14:22:01.102 [TX] set_threshold        |
|  | Channel:        [ 0             ] |  |  HEX: AA 55 06 00 12 00 28 00 4B 8A     |
|  | Low Limit:      [ 20.0       °C ] |  |  FIELDS: {channel: 0, low: 20.0}       |
|  | High Limit:     [ 75.0       °C ] |  |                                         |
|  | Alert Enable:   [ ON (toggle)   ] |  |  14:22:01.120 [RX] status_reply         |
|  +-----------------------------------+  |  HEX: AA 55 02 00 92 00 3C 12           |
|  [ SEND COMMAND ]                       |  FIELDS: {status: "OK", code: 0}        |
+-----------------------------------------+-----------------------------------------+
|  TELEMETRY & SENSOR MONITOR (Charts & Live Indicators)                            |
|  Temperature: [ 24.3 °C ]    Humidity: [ 52.1 % ]    Battery: [ 3280 mV ]          |
+---------------------------------------------------------------------------------+
```
[[CAPTION:Figure]] ASCII layout of the auto-generated dynamic web UI.

---

## 4. WebSocket Protocol Specification

The WebSocket connection (`ws://127.0.0.1:8080/ws/serial`) exchanges structured JSON messages:

### 4.1 Client-to-Server Messages
- **`connect`**: `{ "action": "connect", "port": "COM3", "baudrate": 115200, "virtual": false }`
- **`disconnect`**: `{ "action": "disconnect" }`
- **`send_command`**: `{ "action": "send_command", "command": "set_threshold", "params": {"channel": 0, "low_limit": 20.0} }`
- **`send_raw`**: `{ "action": "send_raw", "hex": "AA550100" }`

### 4.2 Server-to-Client Messages
- **`packet_event`**:
  ```json
  {
    "type": "packet",
    "timestamp": 1726950121.102,
    "direction": "rx",
    "raw_hex": "AA 55 06 00 12 00 28 00 4B 8A",
    "command_id": "0x12",
    "command_name": "temperature_report",
    "crc_valid": true,
    "fields": {
      "channel": 0,
      "temperature": 24.5
    }
  }
  ```
- **`status_event`**: `{ "type": "status", "connected": true, "port": "COM3", "error": null }`
