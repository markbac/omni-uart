"""Unit tests for zero-dependency CRC and checksum calculation engine."""

import pytest
from omniuart.core.crc import (
    CrcAlgorithm,
    CrcModel,
    calculate_crc,
    calculate_custom_crc,
    format_crc_bytes,
    parse_crc_bytes,
    reflect_bits,
    verify_crc,
)

# Standard ASCII test input vector: "123456789"
TEST_VECTOR_123456789 = b"123456789"


def test_reflect_bits() -> None:
    """Verify bit reflection for various widths."""
    assert reflect_bits(0b10000000, 8) == 0b00000001
    assert reflect_bits(0x01, 8) == 0x80
    assert reflect_bits(0x1234, 16) == 0x2C48
    assert reflect_bits(0x12345678, 32) == 0x1E6A2C48


@pytest.mark.parametrize(
    "algorithm,expected_hex",
    [
        (CrcAlgorithm.NONE, 0),
        (CrcAlgorithm.CRC8, 0xF4),           # SMBus / ITU-T I.432.1
        (CrcAlgorithm.CRC16_MODBUS, 0x4B37), # Modbus RTU (reflected)
        (CrcAlgorithm.CRC16_CCITT, 0x29B1),  # X.25 / CCITT-False
        (CrcAlgorithm.CRC32, 0xCBF43926),    # IEEE 802.3 Ethernet
    ],
)
def test_standard_crc_vectors(algorithm: CrcAlgorithm, expected_hex: int) -> None:
    """Verify standard algorithm presets match established test vectors."""
    result = calculate_crc(TEST_VECTOR_123456789, algorithm)
    assert result == expected_hex, f"{algorithm.value} expected {hex(expected_hex)}, got {hex(result)}"


def test_sum8_and_sum16() -> None:
    """Verify 8-bit and 16-bit additive modulo sums."""
    data = bytes([0x01, 0x02, 0x03, 0x04])
    assert calculate_crc(data, CrcAlgorithm.SUM8) == 0x0A
    assert calculate_crc(data, CrcAlgorithm.SUM16) == 0x000A

    # Overflow wrapping test
    overflow_data = bytes([0xFF, 0x02])
    assert calculate_crc(overflow_data, CrcAlgorithm.SUM8) == 0x01
    assert calculate_crc(overflow_data, CrcAlgorithm.SUM16) == 0x0101


def test_xor_checksum() -> None:
    """Verify longitudinal redundancy check (XOR)."""
    data = bytes([0xAA, 0x55, 0x01])
    # 0xAA ^ 0x55 = 0xFF; 0xFF ^ 0x01 = 0xFE
    assert calculate_crc(data, CrcAlgorithm.XOR) == 0xFE


def test_custom_rocksoft_model() -> None:
    """Verify arbitrary custom parametric CRC using Rocksoft model parameters."""
    # Test vector: Custom CRC-16 with poly 0x1021, init 0xFFFF, no reflection
    custom_model = CrcModel(
        width=16,
        poly=0x1021,
        init=0xFFFF,
        refin=False,
        refout=False,
        xorout=0x0000,
        endian="big",
    )
    result = calculate_custom_crc(TEST_VECTOR_123456789, custom_model)
    assert result == 0x29B1

    # Test vector: Custom CRC-16 with reflection and XOR (Modbus equivalent)
    modbus_custom = CrcModel(
        width=16,
        poly=0x8005,
        init=0xFFFF,
        refin=True,
        refout=True,
        xorout=0x0000,
        endian="little",
    )
    assert calculate_custom_crc(TEST_VECTOR_123456789, modbus_custom) == 0x4B37


def test_empty_bytes() -> None:
    """Verify calculation on empty byte sequences."""
    assert calculate_crc(b"", CrcAlgorithm.NONE) == 0
    assert calculate_crc(b"", CrcAlgorithm.SUM8) == 0
    assert calculate_crc(b"", CrcAlgorithm.SUM16) == 0
    assert calculate_crc(b"", CrcAlgorithm.XOR) == 0
    assert calculate_crc(b"", CrcAlgorithm.CRC16_MODBUS) == 0
    assert calculate_crc(b"", CrcAlgorithm.CRC32) == 0


def test_format_and_parse_crc_bytes() -> None:
    """Verify formatting CRC integer to frame bytes and parsing it back."""
    # 16-bit little endian
    crc_val = 0x4B37
    raw_le = format_crc_bytes(crc_val, 16, endian="little")
    assert raw_le == bytes([0x37, 0x4B])
    assert parse_crc_bytes(raw_le, 16, endian="little") == crc_val

    # 16-bit big endian
    raw_be = format_crc_bytes(crc_val, 16, endian="big")
    assert raw_be == bytes([0x4B, 0x37])
    assert parse_crc_bytes(raw_be, 16, endian="big") == crc_val

    # 32-bit little endian
    crc32_val = 0xCBF43926
    raw_crc32 = format_crc_bytes(crc32_val, 32, endian="little")
    assert raw_crc32 == bytes([0x26, 0x39, 0xF4, 0xCB])
    assert parse_crc_bytes(raw_crc32, 32, endian="little") == crc32_val


def test_verify_crc_helper() -> None:
    """Verify the verify_crc helper function."""
    assert verify_crc(TEST_VECTOR_123456789, 0x4B37, CrcAlgorithm.CRC16_MODBUS) is True
    assert verify_crc(TEST_VECTOR_123456789, 0x9999, CrcAlgorithm.CRC16_MODBUS) is False
