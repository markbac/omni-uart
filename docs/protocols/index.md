# Discovered Hardware Protocols & AsyncAPI Specifications

Below is the complete catalog of auto-discovered hardware UART protocols with detailed parameters, command signatures, and formal AsyncAPI 2.6.0 specifications.

### [AsciiDevice](ascii_device.md) (v1.0.0)
- **Description**: Delimited ASCII command protocol (AT-command style)
- **Framing**: `DELIMITED` | **Baudrate**: `115200 bps` | **Commands**: `2`
- **AsyncAPI**: [YAML Spec](asyncapi/ascii_device.yaml) | [Interactive HTML Viewer](asyncapi/ascii_device.html)

### [AT Command Set for a GSM/Cellular Modem (Hayes + 3GPP TS 27.007 subset)](at-commands-uart-interface.md) (vV.250 / TS 27.007)
- **Description**: Plain text command/response lines. No length field, no CRC, and no escaping -- a delimiter-framed protocol with only an end marker, CRLF, for almost every message. One command (SendSmsBody) is the exception: its body is terminated by Ctrl-Z instead, via endDelimiterOverride -- see its own description.
- **Framing**: `DELIMITED` | **Baudrate**: `9600 bps` | **Commands**: `62`
- **AsyncAPI**: [YAML Spec](asyncapi/at-commands-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/at-commands-uart-interface.html)

### [Generic MCU serial bootloader (illustrative, sync-byte auto-baud)](autobaud-bootloader-uart-interface.md) (villustrative)
- **Description**: Not modelling any specific vendor's exact protocol -- illustrates the auto-baud mechanism common to several real MCU ROM bootloaders.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `4`
- **AsyncAPI**: [YAML Spec](asyncapi/autobaud-bootloader-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/autobaud-bootloader-uart-interface.html)

### [BACnet MS/TP (Master-Slave/Token-Passing)](bacnet-mstp-uart-interface.md) (vANSI/ASHRAE 135)
- **Description**: Building-automation token-passing bus over RS-485. Has TWO independent CRCs in one frame: a header CRC and a separate data CRC -- and the data CRC is entirely absent when there's no data, not just zero-length.
- **Framing**: `BINARY` | **Baudrate**: `9600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/bacnet-mstp-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/bacnet-mstp-uart-interface.html)

### [BinarySensorNode](binary_sensor_node.md) (v1.1.0+hw.revB.fw.2.0.1)
- **Description**: Binary UART protocol for multi-channel environmental sensor node with CRC16-Modbus
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `3`
- **AsyncAPI**: [YAML Spec](asyncapi/binary_sensor_node.yaml) | [Interactive HTML Viewer](asyncapi/binary_sensor_node.html)

### [COBS-framed sensor stream](cobs-uart-interface.md) (v1.0)
- **Description**: Consistent Overhead Byte Stuffing: the encoding itself guarantees the delimiter byte (0x00) never appears in the encoded data, so -- unlike delimiter-framed -- no escapeByte is needed at all.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/cobs-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/cobs-uart-interface.html)

### [Serial console (VT100-style CLI), software flow control](console-xonxoff-uart-interface.md) (villustrative)
- **Description**: Many console/CLI serial ports are wired with only TX/RX/GND -- no RTS/CTS lines exist to carry hardware flow control, so XON/XOFF (software, in-band) is the only option when the far end needs to pace output.
- **Framing**: `DELIMITED` | **Baudrate**: `9600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/console-xonxoff-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/console-xonxoff-uart-interface.html)

### [CustomCrcDevice](custom_crc_device.md) (v1.0.0+hw.v2.sha29b1)
- **Description**: Proprietary embedded device demonstrating fully custom Rocksoft-modeled CRC-16
- **Framing**: `BINARY` | **Baudrate**: `230400 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/custom_crc_device.yaml) | [Interactive HTML Viewer](asyncapi/custom_crc_device.html)

### [DMX512](dmx512-uart-interface.md) (vUSITT DMX512-A)
- **Description**: Unidirectional lighting-control broadcast. Frame boundary is a UART break condition (an extended low period), not a byte value, not silence, and not an identifier lookup -- none of which this schema's framing styles model precisely.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/dmx512-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/dmx512-uart-interface.html)

### [DNP3 (Distributed Network Protocol), serial data link layer](dnp3-uart-interface.md) (vDNP3-2013)
- **Description**: SCADA/utility protocol. Its data-link CRC is exactly this schema's existing crc-16-dnp preset -- unused since it was first added several rounds ago. Its real structural novelty: data is chunked into 16-byte blocks, EACH with its own trailing CRC, not one check for the whole frame.
- **Framing**: `BINARY` | **Baudrate**: `9600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/dnp3-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/dnp3-uart-interface.html)

### [Illustrative Frequency-Hopping Combat Net Radio Control Interface (fictional)](fh-radio-uart-interface.md) (v0.1-illustrative)
- **Description**: NOT derived from, or a model of, any specific fielded system's published ICD -- no such document is publicly available. Built only from unclassified, widely-taught operator-level concepts (net ID, hopset/keyset selection by index, time-of-day sync, channel lockout, single-channel fallback) to exercise the schema against this domain without claiming to be real.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `5`
- **AsyncAPI**: [YAML Spec](asyncapi/fh-radio-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/fh-radio-uart-interface.html)

### [Bluetooth HCI UART Transport (H4)](hci-h4-uart-interface.md) (v5.4)
- **Description**: Host <-> Bluetooth radio controller link. Includes HCI_Set_AFH_Host_Channel_Classification, which is literally a frequency-hopping control command: it tells the radio which of Bluetooth's 79 hop channels to avoid. No checksum at all -- H4 relies entirely on the underlying UART/transport for integrity.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `2`
- **AsyncAPI**: [YAML Spec](asyncapi/hci-h4-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/hci-h4-uart-interface.html)

### [SAE J1708](j1708-uart-interface.md) (vJ1708)
- **Description**: Heavy-vehicle diagnostic multi-drop bus. Fixed 9600 8N1 -- no parity at all, unlike M-Bus's 8E1 or G460's default -- a third distinct combination across the protocols tried so far.
- **Framing**: `DELIMITED` | **Baudrate**: `9600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/j1708-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/j1708-uart-interface.html)

### [LIN Bus (classic checksum)](lin-uart-interface.md) (v2.0)
- **Description**: Automotive master/slave bus. Genuinely UART-based (8N1 async bytes) but frame length is looked up by identifier, not sent on the wire.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/lin-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/lin-uart-interface.html)

### [MAVLink FTP](mavlink-ftp-uart-interface.md) (vMAVLink v1/v2 FILE_TRANSFER_PROTOCOL (msg 110))
- **Description**: File transfer nested inside a normal MAVLink message: every FTP packet, of whatever kind, is the SAME outer message type, distinguished only by an inner opcode/offset/session sub-header.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `2`
- **AsyncAPI**: [YAML Spec](asyncapi/mavlink-ftp-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/mavlink-ftp-uart-interface.html)

### [MAVLink v1](mavlink-v1-uart-interface.md) (v1.0)
- **Description**: Drone/autopilot telemetry protocol. Header fields (seq/sysid/compid/msgid) sit between the length field and the region LEN actually counts.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/mavlink-v1-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/mavlink-v1-uart-interface.html)

### [M-Bus (EN 13757-2/3), long/control frame](mbus-long-uart-interface.md) (vEN 13757-2)
- **Description**: START L L START C A CI DATA CHECKSUM STOP -- the length is sent twice and the start byte repeats after it, both as on-wire redundancy checks; a STOP byte closes the frame after the checksum too.
- **Framing**: `BINARY` | **Baudrate**: `9600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/mbus-long-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/mbus-long-uart-interface.html)

### [M-Bus (EN 13757-2/3), short frame](mbus-short-uart-interface.md) (vEN 13757-2)
- **Description**: Utility meter readout bus. 8E1 -- even parity, a format neither G460 nor any earlier test used -- at one of several fixed baud rates the spec enumerates (300/600/1200/2400/4800/9600).
- **Framing**: `DELIMITED` | **Baudrate**: `9600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/mbus-short-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/mbus-short-uart-interface.html)

### [Generic MCU normal operation (illustrative)](mcu-normal-mode-uart-interface.md) (villustrative)
- **Description**: Minimal stand-in application-mode protocol, existing only to demonstrate a fully-specified relatedInterfaces transition into the auto-baud bootloader above.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `2`
- **AsyncAPI**: [YAML Spec](asyncapi/mcu-normal-mode-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/mcu-normal-mode-uart-interface.html)

### [Modbus ASCII](modbus-ascii-uart-interface.md) (v1.0)
- **Description**: Modbus over serial, ASCII transmission mode. Every logical byte is sent as 2 ASCII hex characters, framed between ':' and CRLF.
- **Framing**: `DELIMITED` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/modbus-ascii-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/modbus-ascii-uart-interface.html)

### [Modbus RTU](modbus-rtu-uart-interface.md) (v1.0)
- **Description**: Modbus over serial, RTU transmission mode. Frame boundaries are marked by line silence rather than sync bytes or a length field.
- **Framing**: `DELIMITED` | **Baudrate**: `115200 bps` | **Commands**: `2`
- **AsyncAPI**: [YAML Spec](asyncapi/modbus-rtu-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/modbus-rtu-uart-interface.html)

### [9-bit UART multidrop addressing](multidrop-9bit-uart-interface.md) (vgeneric (common 8051/PIC UART mode))
- **Description**: RS-485 multidrop scheme common on small microcontroller UARTs: a 9th data bit (not parity) flags whether a byte is an ADDRESS (bit=1) or DATA (bit=0), so slaves can filter in hardware without the CPU inspecting every byte. dataBits=9 was already a valid enum value but never actually exercised until now.
- **Framing**: `BINARY` | **Baudrate**: `9600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/multidrop-9bit-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/multidrop-9bit-uart-interface.html)

### [NMEA 0183](nmea0183-uart-interface.md) (v4.11)
- **Description**: ASCII, delimiter-framed sentence protocol used by GPS/marine navigation equipment. No commands/responses in the request-reply sense -- the device streams sentences unsolicited.
- **Framing**: `DELIMITED` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/nmea0183-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/nmea0183-uart-interface.html)

### [PPP (HDLC-like async framing, RFC 1662)](ppp-uart-interface.md) (vRFC 1662)
- **Description**: Escapes any occurrence of the flag/escape bytes (and, by default, control chars <0x20) by transmitting escapeByte then (originalByte XOR 0x20) -- a general transform rule, not SLIP's fixed substitute-byte-pair table.
- **Framing**: `DELIMITED` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/ppp-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/ppp-uart-interface.html)

### [PPPoS (PPP over Serial, e.g. to a GSM/cellular modem)](pppos-uart-interface.md) (vRFC 1662, over a serial modem link)
- **Description**: Same async HDLC framing as plain PPP, but hardware flow control isn't optional here: the underlying radio/modem can stall mid-transmission, and without RTS/CTS pacing the host will overrun its buffer.
- **Framing**: `DELIMITED` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/pppos-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/pppos-uart-interface.html)

### [SCPI (Standard Commands for Programmable Instruments) over RS-232](scpi-uart-interface.md) (vSCPI-99 / IEEE 488.2)
- **Description**: ASCII line-based instrument control (oscilloscopes, PSUs, DMMs). Baud is configured manually on both sides -- no auto-negotiation -- and commonly must match exactly or the instrument just doesn't respond, with no error reported at all. Chains multiple independent commands onto one physical line via ';', which compoundMessageDelimiter exists specifically for.
- **Framing**: `DELIMITED` | **Baudrate**: `9600 bps` | **Commands**: `4`
- **AsyncAPI**: [YAML Spec](asyncapi/scpi-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/scpi-uart-interface.html)

### [Single-wire half-duplex UART link (illustrative)](single-wire-uart-interface.md) (villustrative)
- **Description**: A genuine single shared data line, not just RTS/CTS omitted -- both sides' TX and RX are the same open-drain/tri-state pin, common on microcontroller debug or bootload pins wired for minimal pin count.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/single-wire-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/single-wire-uart-interface.html)

### [SLIP (Serial Line Internet Protocol)](slip-uart-interface.md) (vRFC 1055)
- **Description**: Pure framing protocol -- carries an arbitrary encapsulated packet (typically IP) with no application-level commands or integrity check of its own.
- **Framing**: `DELIMITED` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/slip-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/slip-uart-interface.html)

### [SmartActuator](smart_actuator.md) (v2.0.0)
- **Description**: Servo actuator protocol with CRC32 integrity checking and status reporting
- **Framing**: `BINARY` | **Baudrate**: `921600 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/smart_actuator.yaml) | [Interactive HTML Viewer](asyncapi/smart_actuator.html)

### [u-blox UBX](ubx-uart-interface.md) (v34)
- **Description**: GPS/GNSS receiver binary protocol. class+id sit between the sync pattern and the length field -- before the length-counted region, unlike MAVLink's after.
- **Framing**: `BINARY` | **Baudrate**: `9600 bps` | **Commands**: `2`
- **AsyncAPI**: [YAML Spec](asyncapi/ubx-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/ubx-uart-interface.html)

### [XBee API Mode](xbee-api-uart-interface.md) (vS2C Zigbee firmware)
- **Description**: Digi XBee radio module binary command protocol, including an AT Command frame setting ATCH (the RF channel/frequency).
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `1`
- **AsyncAPI**: [YAML Spec](asyncapi/xbee-api-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/xbee-api-uart-interface.html)

### [XMODEM (checksum variant)](xmodem-uart-interface.md) (vclassic)
- **Description**: File transfer over a serial link. Mixes 128/1024-byte framed data blocks (selected by leading byte, not a length field) with completely bare single-byte control codes -- no envelope at all around ACK/NAK/EOT/CAN.
- **Framing**: `BINARY` | **Baudrate**: `115200 bps` | **Commands**: `4`
- **AsyncAPI**: [YAML Spec](asyncapi/xmodem-uart-interface.yaml) | [Interactive HTML Viewer](asyncapi/xmodem-uart-interface.html)
