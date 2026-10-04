import pytest
from omniuart.core.models import FieldSpec, FieldType
from omniuart.core.codec import encode_fields, decode_fields, encode_value, decode_value

def test_scaling_and_offset():
    spec = FieldSpec(name="temp", type=FieldType.INT16, scale=0.1, offset_val=-40.0)
    # real_val = raw * 0.1 - 40.0 => raw = (25.0 - (-40.0)) / 0.1 = 650
    encoded = encode_value(spec, 25.0)
    decoded = decode_value(spec, encoded)
    assert round(decoded, 1) == 25.0

def test_custom_encoding():
    spec = FieldSpec(name="label", type=FieldType.STRING, length=4, encoding="ascii")
    encoded = encode_value(spec, "OK")
    assert encoded == b"OK\x00\x00"
    decoded = decode_value(spec, encoded)
    assert decoded == "OK"

def test_bit_width_validation():
    spec = FieldSpec(name="flags", type=FieldType.UINT8, bit_width=4)
    # max value for 4 bits is 15
    encoded = encode_value(spec, 15)
    assert encoded == b"\x0f"
    with pytest.raises(Exception):
        encode_value(spec, 16)

def test_length_ref_and_count_ref():
    specs = [
        FieldSpec(name="len", type=FieldType.UINT8),
        FieldSpec(name="data", type=FieldType.BYTES, length_ref="len"),
        FieldSpec(name="count", type=FieldType.UINT8),
        FieldSpec(name="values", type=FieldType.UINT16, is_array=True, item_type=FieldType.UINT16, count_ref="count"),
    ]

    payload = bytes([0x03, 0xAA, 0xBB, 0xCC, 0x02, 0x01, 0x00, 0x02, 0x00])
    decoded = decode_fields(specs, payload)

    assert decoded["len"] == 3
    assert decoded["data"] == "aabbcc"
    assert decoded["count"] == 2
    assert decoded["values"] == [1, 2]

def test_conditional_fields_and_discriminator():
    specs = [
        FieldSpec(name="type", type=FieldType.UINT8),
        FieldSpec(name="int_val", type=FieldType.UINT16, discriminator="type", discriminator_value=1),
        FieldSpec(name="str_val", type=FieldType.STRING, length=4, discriminator="type", discriminator_value=2),
    ]

    # Type 1: payload contains uint16
    p1 = bytes([0x01, 0x34, 0x12])
    d1 = decode_fields(specs, p1)
    assert d1["type"] == 1
    assert d1["int_val"] == 0x1234
    assert "str_val" not in d1

    # Type 2: payload contains string
    p2 = bytes([0x02, ord('A'), ord('B'), ord('C'), ord('D')])
    d2 = decode_fields(specs, p2)
    assert d2["type"] == 2
    assert d2["str_val"] == "ABCD"
    assert "int_val" not in d2

def test_nested_fields():
    sub_fields = [
        FieldSpec(name="x", type=FieldType.INT8),
        FieldSpec(name="y", type=FieldType.INT8),
    ]
    spec = FieldSpec(name="point", type=FieldType.BYTES, nested_fields=sub_fields)

    data = encode_value(spec, {"x": -5, "y": 10})
    assert data == bytes([0xFB, 0x0A])
    decoded = decode_value(spec, data)
    assert decoded == {"x": -5, "y": 10}
