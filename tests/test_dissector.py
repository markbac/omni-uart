import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import FrameCodec
from omniuart.core.dissector import dissect_frame, DissectedFrame, FieldSlice

def test_dissect_frame():
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node.yaml")
    assert spec is not None

    codec = FrameCodec(spec)
    raw = codec.encode_command("ping", {})

    dissected = dissect_frame(spec, raw)

    assert dissected.valid
    assert dissected.command_name == "ping"

    text = dissected.format_diagnostic_text()
    assert "FRAME DISSECTION" in text
    assert "ping" in text
