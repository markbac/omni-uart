"""Unit tests for Declarative Device UI Schema subsystem (#229)."""

from pathlib import Path
import pytest

from omniuart.core.device_ui import DeviceUISpec, load_device_ui, generate_device_ui_schema


def test_device_ui_model_creation():
    ui_dict = {
        "identity": {
            "name": "Test Actuator",
            "model": "ACT-100",
        },
        "protocol_ref": "smart_actuator",
        "panels": [
            {
                "name": "main",
                "title": "Main Panel",
                "groups": [
                    {
                        "name": "control",
                        "title": "Position Control",
                        "widgets": [
                            {
                                "widget_type": "slider",
                                "field_ref": "target_position",
                                "label": "Target Position",
                                "min": 0,
                                "max": 100,
                            }
                        ],
                    }
                ],
            }
        ],
    }

    spec = load_device_ui(ui_dict)
    assert isinstance(spec, DeviceUISpec)
    assert spec.identity.name == "Test Actuator"
    assert len(spec.panels) == 1
    assert spec.panels[0].groups[0].widgets[0].widget_type == "slider"


def test_device_ui_load_yaml_fixture():
    fixture_path = Path("examples/device_ui/binary_sensor_node_ui.yaml")
    assert fixture_path.exists()

    spec = load_device_ui(fixture_path)
    assert spec.identity.name == "Environmental Sensor Node"
    assert spec.protocol_ref == "binary_sensor_node"
    assert len(spec.panels) == 2


def test_generate_device_ui_schema():
    schema = generate_device_ui_schema()
    assert isinstance(schema, dict)
    assert "$defs" in schema or "properties" in schema
    assert "identity" in schema["properties"]
