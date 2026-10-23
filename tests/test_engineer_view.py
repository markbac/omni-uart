"""Unit tests for Engineer Raw-Protocol Diagnostic View (#234)."""

from pathlib import Path
from omniuart.core.models import load_protocol
from omniuart.core.session import Exchange, ExchangeStatus
from omniuart.core.codec import DecodedFrame
from omniuart.core.engineer_view import EngineerProtocolView, ProtocolExchangeDetail


def test_engineer_view_inspection():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    spec = load_protocol(proto_file)

    view = EngineerProtocolView(spec)

    req_bytes = b"\xAA\x55\x01\x00\x01\x00\xB0\x55\xAA"
    resp_bytes = b"\xAA\x55\x04\x00\x81\x00\x00\x00\x00\x62\xDE\x55\xAA"

    frame = DecodedFrame(raw=resp_bytes, name="ping", fields={"uptime_seconds": 10})
    ex = Exchange(command="ping", request=req_bytes, status=ExchangeStatus.OK, response_bytes=resp_bytes, response=frame, latency_ms=12.5)

    detail = view.inspect_exchange(ex)
    assert isinstance(detail, ProtocolExchangeDetail)
    assert detail.command_name == "ping"
    assert detail.latency_ms == 12.5
    assert detail.crc_algorithm == "crc16_modbus"
    assert "AA 55" in detail.request_raw_hex
    assert len(detail.response_field_slices) > 0

    html = view.render_engineer_html_summary(detail.exchange_id)
    assert "Engineer Raw Protocol Detail" in html
    assert "ping" in html


def test_engineer_view_escaping_hostile_inputs():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    spec = load_protocol(proto_file)
    view = EngineerProtocolView(spec)

    # 1. Unknown exchange with HTML in ID
    missing_html = view.render_engineer_html_summary("<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in missing_html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in missing_html

    # 2. Hostile command name and decoded field value
    req_bytes = b"\xAA\x55\x01\x00\x01\x00\xB0\x55\xAA"
    resp_bytes = b"\xAA\x55\x04\x00\x81\x00\x00\x00\x00\x62\xDE\x55\xAA"
    frame = DecodedFrame(raw=resp_bytes, name="<b onmouseover=alert(1)>", fields={"status": "<script>alert(2)</script>"})
    ex = Exchange(command="<img src=x onerror=alert(3)>", request=req_bytes, status=ExchangeStatus.OK, response_bytes=resp_bytes, response=frame, latency_ms=10.0)

    _ = view.inspect_exchange(ex, exchange_id="ex_<test>")
    html = view.render_engineer_html_summary("ex_<test>")

    assert "<img src=x onerror=alert(3)>" not in html
    assert "&lt;img src=x onerror=alert(3)&gt;" in html
    assert "ex_&lt;test&gt;" in html
