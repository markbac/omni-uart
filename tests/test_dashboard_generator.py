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
