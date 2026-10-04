import pytest
from omniuart.core.plugin import plugin_registry, ProtocolPlugin
from omniuart.core.crc import calculate_crc
from omniuart.core.codec import encode_value, decode_value
from omniuart.core.models import FieldSpec, FieldType

def test_custom_plugin_registration():
    plugin = ProtocolPlugin("my_custom_plugin")

    # Custom encoding: rot13 / bCD
    plugin.encodings["custom_bcd"] = (
        lambda val: bytes([int(val) & 0xFF]),
        lambda data: int(data[0])
    )

    # Custom checksum: xor_sum
    def xor_sum(data: bytes) -> int:
        res = 0
        for b in data:
            res ^= b
        return res

    plugin.checksums["xor8"] = xor_sum

    plugin_registry.register_plugin(plugin)

    # Verify custom checksum via calculate_crc
    assert calculate_crc(b"\x01\x02\x04", "xor8") == 7

    # Verify custom encoding via codec
    fspec = FieldSpec(name="bcd_val", type=FieldType.BYTES, encoding="custom_bcd")
    encoded = encode_value(fspec, 42)
    assert encoded == b"*"
    decoded = decode_value(fspec, encoded)
    assert decoded == 42
