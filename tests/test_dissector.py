from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import FrameCodec
from omniuart.core.dissector import dissect_frame

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


def test_dissector_offsets_include_length_and_id_and_report_crc():
    """Payload offsets start after header, length and command id; a corrupted CRC shows both values (#329)."""
    from omniuart.core.catalog import CatalogManager
    from omniuart.core.codec import FrameCodec
    from omniuart.core.dissector import dissect_frame

    spec = CatalogManager().get_protocol("binary_sensor_node")
    cmd = spec.get_command("get_readings")
    raw = FrameCodec(spec).encode_command(cmd, {"channel": 3})
    slices = {s.field_name: s for s in dissect_frame(spec, raw).field_slices}
    assert [slices[n].start_offset for n in ("header", "length", "command_id", "channel")] == [0, 2, 4, 5]
    assert slices["channel"].decoded_value == 3

    bad = bytearray(raw)
    bad[-3] ^= 0xFF  # the integrity field sits just before the 2-byte footer
    info = dissect_frame(spec, bytes(bad)).crc_info
    assert info is not None and info["valid"] is False
    assert info["calculated"] != info["received"]
