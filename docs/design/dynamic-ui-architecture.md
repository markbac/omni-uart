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

## 3. UI Component Layout & Session Controls

The interface is structured into four primary viewports:

```
+---------------------------------------------------------------------------------+
|  OmniUART [Protocol: SensorNode v1.2]   [Port: COM4 v] [Baud: 115200 v] [CONNECT] |
|  [x] Virtual Loopback Mode    [Traffic: TX 142pkts / RX 140pkts]   [Status: ACTIVE] |
|  SESSION RECORDER: [● START REC] [❚❚ PAUSE]  Frames: 282  Bytes: 3.4KB            |
|                    [EXPORT: JSONL v] [DOWNLOAD RECORDING]                       |
+---------------------------------------------------------------------------------+
|  COMMAND DISPATCH (Dynamic)             |  DUAL-VIEW PACKET INSPECTOR             |
|                                         |  [All] [TX Only] [RX Only] [Clear Log]  |
|  Command: [set_threshold          v]    |                                         |
|  +-----------------------------------+  |  14:22:01.102 [TX] set_threshold        |
|  | Channel:        [ 0             ] |  |  RAW HEX: [AA 55] [06 00] [12] [28 00]  |
|  | Low Limit:      [ 20.0       °C ] |  |           (Hdr)   (Len)   (Cmd)(Data)   |
|  | High Limit:     [ 75.0       °C ] |  |  DECODED: {channel: 0, low: 20.0}       |
|  | Alert Enable:   [ ON (toggle)   ] |  |  DEBUG: CRC16 Valid (0x4B8A, bytes 2..7)|
|  +-----------------------------------+  |                                         |
|  [ SEND COMMAND ]                       |  14:22:01.120 [RX] status_reply         |
|                                         |  RAW HEX: [AA 55] [02 00] [92] [00]     |
|                                         |  DECODED: {status: "OK", code: 0}        |
+-----------------------------------------+-----------------------------------------+
|  TELEMETRY & SENSOR MONITOR (Charts & Live Indicators)                            |
|  Temperature: [ 24.3 °C ]    Humidity: [ 52.1 % ]    Battery: [ 3280 mV ]          |
+---------------------------------------------------------------------------------+
```
[[CAPTION:Figure]] ASCII layout of the auto-generated dynamic web UI with session recorder.

### 3.1 Dual-View Raw and Decoded Stream Inspector
- **Raw Stream View**: Hexadecimal bytes paired with ASCII representations. Bytes are colored by semantic section:
  - Header sync bytes: Light Blue
  - Length field: Yellow
  - Command ID: Green
  - Parameter payloads: Purple
  - Checksum/CRC: Green (if verified) or Red (if invalid)
  - Footer bytes: Gray
- **Decoded View**: Tree view showing parameter names, decoded types, calculated engineering values, and units.
- **Interactive Cross-Highlighting**: Hovering over any parameter in the Decoded Tree highlights the exact corresponding byte span in the Raw Hex View.
- **CRC Debug Drawer**: Clicking any packet displays a breakdown showing:
  - Algorithm used (e.g. `crc16_modbus` or custom Rocksoft parameters).
  - Expected CRC vs Received CRC.
  - Byte slice indices evaluated.

---

## 4. WebSocket Protocol Specification

The WebSocket connection (`ws://127.0.0.1:8080/ws/serial`) exchanges structured JSON messages:

### 4.1 Client-to-Server Messages
- **`connect`**: `{ "action": "connect", "port": "COM3", "baudrate": 115200, "virtual": false }`
- **`disconnect`**: `{ "action": "disconnect" }`
- **`send_command`**: `{ "action": "send_command", "command": "set_threshold", "params": {"channel": 0, "low_limit": 20.0} }`
- **`send_raw`**: `{ "action": "send_raw", "hex": "AA550100" }`
- **`start_record`**: `{ "action": "start_record", "session_name": "thermal_run_1" }`
- **`stop_record`**: `{ "action": "stop_record" }`
- **`export_session`**: `{ "action": "export_session", "format": "jsonl" | "csv" | "bin" }`

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
    "crc_details": {
      "algorithm": "crc16_modbus",
      "expected": "0x4B8A",
      "received": "0x4B8A",
      "byte_range": [2, 8]
    },
    "fields": {
      "channel": 0,
      "temperature": 24.5
    },
    "slices": [
      {"role": "header", "start": 0, "end": 2},
      {"role": "length", "start": 2, "end": 4},
      {"role": "command_id", "start": 4, "end": 5},
      {"role": "payload", "start": 5, "end": 9},
      {"role": "crc", "start": 9, "end": 11}
    ]
  }
  ```
- **`status_event`**: `{ "type": "status", "connected": true, "port": "COM3", "recording": true, "packet_count": 282, "error": null }`
- **`session_export`**: `{ "type": "session_export", "format": "jsonl", "filename": "session_20260921.jsonl", "data": "..." }`
