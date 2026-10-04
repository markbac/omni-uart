import pytest
import asyncio
from omniuart.core.simulator import BaseDeviceSimulator, DeclarativeBehavior, SimulatorRule
from omniuart.core.models import ProtocolSpec, FramingConfig, FramingType, SerialConfig, ProtocolMeta
from omniuart.core.transport import VirtualTransport

@pytest.fixture
def ascii_spec():
    return ProtocolSpec(
        metadata=ProtocolMeta(name="ascii_test", version="1.0"),
        serial_config=SerialConfig(baudrate=9600),
        framing=FramingConfig(type=FramingType.DELIMITED, suffix="\r\n"),
        commands=[]
    )

def test_declarative_simulator_rules_direct(ascii_spec):
    behavior = DeclarativeBehavior(
        initial_state={"status": "IDLE", "count": 0},
        rules=[
            SimulatorRule(
                match_pattern="STATUS",
                response_template="STATUS={status}\r\n"
            ),
            SimulatorRule(
                match_pattern="START",
                state_updates={"status": "RUNNING"},
                response_template="OK\r\n"
            )
        ]
    )

    sim = BaseDeviceSimulator(spec=ascii_spec, behavior=behavior)

    resp1 = sim.process_incoming_bytes(bytearray(b"STATUS\r\n"))
    assert resp1 == b"STATUS=IDLE\r\n"

    resp2 = sim.process_incoming_bytes(bytearray(b"START\r\n"))
    assert resp2 == b"OK\r\n"

    resp3 = sim.process_incoming_bytes(bytearray(b"STATUS\r\n"))
    assert resp3 == b"STATUS=RUNNING\r\n"
