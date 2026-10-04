"""Unit tests for Device Explorer and Device Navigation Model (#232)."""

from pathlib import Path
from omniuart.core.models import load_protocol
from omniuart.core.device_explorer import (
    DeviceExplorer,
    DeviceNode,
    DeviceSection,
    build_navigation_tree_from_spec,
)


def test_build_navigation_tree_from_spec():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    spec = load_protocol(proto_file)

    tree = build_navigation_tree_from_spec(spec)
    assert len(tree) >= 4

    sections = [node.section for node in tree]
    assert DeviceSection.OVERVIEW in sections
    assert DeviceSection.CONNECTIVITY in sections
    assert DeviceSection.METERING in sections
    assert DeviceSection.CONFIGURATION in sections


def test_device_explorer_discovery():
    explorer = DeviceExplorer()
    devices = explorer.discover_catalog_devices()

    assert len(devices) > 0
    names = [d.name for d in devices]
    assert "BinarySensorNode" in names or any("sensor" in n.lower() for n in names)


def test_device_explorer_register_active():
    proto_file = Path("examples/protocols/binary_sensor_node.yaml")
    spec = load_protocol(proto_file)

    explorer = DeviceExplorer()
    node = explorer.register_active_device("dev_001", spec, port_or_address="COM3")

    assert node.id == "dev_001"
    assert node.connection_state == "connected"
    assert node.port_or_address == "COM3"
    assert "dev_001" in explorer.active_devices

    d_dict = node.to_dict()
    assert d_dict["id"] == "dev_001"
    assert len(d_dict["sections"]) > 0
