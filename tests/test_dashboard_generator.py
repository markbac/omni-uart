"""Unit tests for Generated Device Control Console Dashboard (#230)."""

from pathlib import Path
from omniuart.core.models import load_protocol
from omniuart.core.device_ui import load_device_ui
from omniuart.dashboard_generator import generate_device_dashboard_html


def test_dashboard_generation_default():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    assert proto_file.exists()

    spec = load_protocol(proto_file)
    html = generate_device_dashboard_html(spec)

    assert "Device Control Console" in html
    assert "BinarySensorNode" in html or "CONNECTED" in html


def test_dashboard_generation_with_ui_spec():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    ui_file = Path("examples/device_ui/binary_sensor_node_ui.yaml")

    spec = load_protocol(proto_file)
    ui_spec = load_device_ui(ui_file)

    html = generate_device_dashboard_html(spec, ui_spec)

    assert "Environmental Sensor Node" in html
    assert "Environment Dashboard" in html
    assert "BSN-200" in html


def test_dashboard_escaping_hostile_inputs():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    spec = load_protocol(proto_file)
    spec.metadata.name = "<img src=x onerror=alert(1)>"

    ui_file = Path("examples/device_ui/binary_sensor_node_ui.yaml")
    ui_spec = load_device_ui(ui_file)
    ui_spec.identity.name = "<script>alert('xss')</script>"
    ui_spec.panels[0].groups[0].widgets[0].field_ref = "x');alert(document.cookie);//"
    ui_spec.panels[0].groups[0].widgets[0].label = "<b onmouseover=alert(2)>Click</b>"

    html = generate_device_dashboard_html(spec, ui_spec)

    assert "<script>alert('xss')</script>" not in html
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html
    assert "<b onmouseover=alert(2)>" not in html
    assert "&lt;b onmouseover=alert(2)&gt;" in html
    assert 'onclick="triggerWidget(' not in html
    assert "Content-Security-Policy" in html
