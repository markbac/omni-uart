"""Unit test for intelligent device control generation from field metadata (#231)."""

from pathlib import Path
from omniuart.core.models import FieldSpec, FieldType, CommandSafety, load_protocol
from omniuart.core.device_ui import infer_widget_for_field, infer_device_ui_from_spec, WidgetSpec


def test_infer_widget_for_enum_field():
    f = FieldSpec(name="baud_select", type=FieldType.ENUM, options={1: "9600", 2: "115200"})
    w = infer_widget_for_field(f)
    assert w.widget_type == "dropdown"
    assert w.options == {1: "9600", 2: "115200"}


def test_infer_widget_for_boolean_field():
    f = FieldSpec(name="enable_power", type=FieldType.BOOL)
    w = infer_widget_for_field(f, is_writable=True)
    assert w.widget_type == "switch"

    w_ro = infer_widget_for_field(f, is_writable=False)
    assert w_ro.widget_type == "badge"


def test_infer_widget_for_numeric_range_field():
    f = FieldSpec(name="temp_target", type=FieldType.FLOAT32, min=10.0, max=40.0, unit="°C")
    w = infer_widget_for_field(f)
    assert w.widget_type == "slider"
    assert w.min == 10.0
    assert w.max == 40.0
    assert w.unit == "°C"


def test_infer_device_ui_from_spec():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    spec = load_protocol(proto_file)

    ui = infer_device_ui_from_spec(spec)
    assert ui.identity.name == "BinarySensorNode"
    assert len(ui.panels) == 1
    groups = ui.panels[0].groups
    assert any(g.name == "controls" for g in groups)
    assert any(g.name == "telemetry" for g in groups)
