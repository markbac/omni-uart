import json
from pathlib import Path
from omniuart.core.recorder import SessionRecorder, PacketEvent, Transaction, SessionRecord

def test_session_record_model(tmp_path: Path):
    recorder = SessionRecorder(
        protocol_name="binary_sensor_node",
        transport_metadata={"port": "COM3", "baudrate": 115200, "virtual": False}
    )

    tx_event = recorder.record("tx", b"\xAA\x55\x01\x00\x01\x00\x12\x34", command_name="ping", command_id=1)
    rx_event = recorder.record("rx", b"\xAA\x55\x02\x00\x81\x00\x56\x78", command_name="ping_ack", command_id=1)

    tx_transaction = Transaction(
        transaction_id="tx_001",
        command_name="ping",
        command_id=1,
        tx_event=tx_event,
        rx_events=[rx_event],
        latency_ms=2.5,
        status="ok"
    )
    recorder.add_transaction(tx_transaction)

    json_path = tmp_path / "session_record.json"
    recorder.export_session_json(json_path)

    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))

    assert data["protocol_name"] == "binary_sensor_node"
    assert data["transport_metadata"]["port"] == "COM3"
    assert len(data["events"]) == 2
    assert len(data["transactions"]) == 1
    assert data["transactions"][0]["command_name"] == "ping"
    assert data["transactions"][0]["status"] == "ok"
