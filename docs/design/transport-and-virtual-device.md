# OmniUART Transport Layer & Virtual MCU Design

## 1. Architectural Purpose
The Transport Layer decouples byte-level serialization and message parsing from physical input/output mechanisms. It defines an abstract asynchronous transport interface fulfilled by two primary implementations:
1. **`SerialTransport`**: Communicates with physical serial interfaces (USB-UART bridges, FTDI chips, native RS-232/RS-485 ports).
2. **`VirtualTransport`**: An in-memory mock microcontroller simulator that allows offline protocol development, dynamic UI testing, and automated continuous integration without hardware attached.

---

## 2. Abstract Transport Interface

All transports implement the `AsyncTransport` contract:

```python
class AsyncTransport(ABC):
    @abstractmethod
    async def open(self) -> None:
        """Establish connection to the physical port or initialize virtual buffers."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Release port resources cleanly."""
        pass

    @abstractmethod
    async def write(self, data: bytes) -> int:
        """Transmit raw bytes to the endpoint."""
        pass

    @abstractmethod
    async def read(self, max_bytes: int = 4096) -> bytes:
        """Asynchronously read available incoming bytes."""
        pass

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Indicate whether the transport is active."""
        pass
```
[[CAPTION:Figure]] Transport interface definition.

---

## 3. Physical Serial Transport (`SerialTransport`)

### 3.1 Serial Port Management
The physical serial transport wraps `pyserial` with an asynchronous worker task:
- Non-blocking async queue decoupling: An internal background reader thread reads from the OS serial descriptor into an `asyncio.Queue` to prevent blocking the event loop.
- Dynamic port discovery: Enumerates connected devices using `serial.tools.list_ports`, returning manufacturer, serial number, and product VID/PID for user selection.
- Flow control support: Hardware RTS/CTS, software XON/XOFF, and DTR toggle for target microcontroller reboot.

### 3.2 RS-485 Half-Duplex Operation
For RS-485 transceivers requiring Direction Control (DE/RE pins):
- Custom RTS toggle before and after write operations.
- Settling delay configuration (pre-transmission and post-transmission guard times) to prevent bus collisions.

---

## 4. Virtual MCU Loopback Engine (`VirtualTransport`)

The Virtual MCU simulator makes OmniUART completely self-contained for tests and offline development:

![Transport & Virtual MCU C4 Component Model](../diagrams/images/c4_component_transport.svg)
[[CAPTION:Figure]] C4 Level 3: Transport & Virtual MCU Component Diagram.

```mermaid
flowchart LR
    subgraph Host["OmniUART Application"]
        TX[Client TX Stream]
        RX[Client RX Stream]
    end

    subgraph VirtualMCU["Virtual MCU Engine"]
        InQueue[RX Buffer FIFO]
        Decoder[Virtual Codec Decoder]
        RuleEngine[Response Rule Engine]
        FaultInjector[Fault & Jitter Injector]
        OutQueue[TX Buffer FIFO]
    end

    TX --> InQueue
    InQueue --> Decoder
    Decoder --> RuleEngine
    RuleEngine --> FaultInjector
    FaultInjector --> OutQueue
    OutQueue --> RX
```
[[CAPTION:Figure]] Virtual MCU loopback internal pipeline.

### 4.1 Response Rule Engine
The virtual engine matches incoming command opcodes and returns predetermined responses defined in the protocol:
- **Automatic Echo / Ping Response**: Automatically responds to standard discovery/ping opcodes.
- **Stateful Memory Bank**: Stores simulated device registers (e.g. `set_temperature` updates a virtual sensor register; subsequent `get_temperature` queries return the updated value).
- **Simulated Latency**: Configurable response delay (e.g. 5ms to 50ms) to model real-world microcontroller processing intervals.

### 4.2 Fault & Resilience Injection
For automated reliability testing, the virtual device can inject realistic bus disturbances:
- **Corrupted CRC**: Bit-flips checksum bytes with a configurable probability (e.g. 10% corrupted frames) to test client frame rejection.
- **Byte Dropping**: Truncates frames mid-payload to verify stream synchronization recovery.
- **Intermittent Timeouts**: Simulates firmware lockups by withholding responses.
- **Preamble Noise**: Injects random garbage bytes between frames to verify sync hunt resilience.

```mermaid
sequenceDiagram
    autonumber
    actor Client as OmniUART Client / Script
    participant Virtual as Virtual MCU Engine
    participant Fault as Fault & Jitter Injector

    Client->>Virtual: write(raw_request_bytes)
    Virtual->>Virtual: Decode opcode & update state
    Virtual->>Fault: synthesize_reply(expected_response)
    alt Normal Transmission
        Fault-->>Client: Deliver pristine response (CRC Valid)
    else Fault Injection: Bit-Flipped CRC
        Fault-->>Client: Deliver response with corrupted CRC byte
        Client->>Client: StreamDecoder flags CRC_MISMATCH & logs diff
    else Fault Injection: Byte Drop
        Fault-->>Client: Deliver truncated payload (missing 2 bytes)
        Client->>Client: StreamDecoder buffers fragment until timeout
    else Fault Injection: Preamble Noise
        Fault-->>Client: Deliver 128 bytes garbage + valid frame
        Client->>Client: StreamDecoder sync-hunts and recovers frame
    end
```
[[CAPTION:Figure]] Sequence diagram for Virtual MCU fault and jitter injection.
