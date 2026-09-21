"""Zero-dependency CRC and Checksum Calculation Engine.

Supports standard industrial presets (CRC-8 SMBus, CRC-16 Modbus, CRC-16 CCITT,
CRC-32 IEEE 802.3, Sum8, Sum16, XOR) as well as arbitrary custom parametric CRCs
defined according to the Rocksoft Parameter Model.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Union


class CrcAlgorithm(str, Enum):
    """Enumeration of supported standard CRC presets."""

    NONE = "none"
    SUM8 = "sum8"
    SUM16 = "sum16"
    XOR = "xor"
    CRC8 = "crc8"
    CRC16_MODBUS = "crc16_modbus"
    CRC16_CCITT = "crc16_ccitt"
    CRC32 = "crc32"
    CUSTOM = "custom"


@dataclass(frozen=True)
class CrcModel:
    """Rocksoft Parameter Model defining an arbitrary CRC algorithm."""

    width: int
    poly: int
    init: int
    refin: bool = False
    refout: bool = False
    xorout: int = 0
    endian: str = "little"
    check: Optional[int] = None

    def __post_init__(self) -> None:
        if self.width not in (8, 16, 24, 32):
            raise ValueError(f"CRC width must be 8, 16, 24, or 32 bits, got {self.width}")
        if self.endian not in ("little", "big"):
            raise ValueError(f"Endianness must be 'little' or 'big', got '{self.endian}'")


# Standard Named Presets
PRESET_MODELS: Dict[CrcAlgorithm, CrcModel] = {
    CrcAlgorithm.CRC8: CrcModel(
        width=8,
        poly=0x07,
        init=0x00,
        refin=False,
        refout=False,
        xorout=0x00,
        endian="big",
        check=0xF4,
    ),
    CrcAlgorithm.CRC16_MODBUS: CrcModel(
        width=16,
        poly=0x8005,
        init=0xFFFF,
        refin=True,
        refout=True,
        xorout=0x0000,
        endian="little",
        check=0x4B37,
    ),
    CrcAlgorithm.CRC16_CCITT: CrcModel(
        width=16,
        poly=0x1021,
        init=0xFFFF,
        refin=False,
        refout=False,
        xorout=0x0000,
        endian="big",
        check=0x29B1,
    ),
    CrcAlgorithm.CRC32: CrcModel(
        width=32,
        poly=0x04C11DB7,
        init=0xFFFFFFFF,
        refin=True,
        refout=True,
        xorout=0xFFFFFFFF,
        endian="little",
        check=0xCBF43926,
    ),
}

# Precomputed lookup tables cache for high-throughput calculation
_TABLE_CACHE: Dict[CrcModel, List[int]] = {}


def reflect_bits(val: int, width: int) -> int:
    """Reflect the bit order of an integer of specified width."""
    res = 0
    for i in range(width):
        if (val >> i) & 1:
            res |= 1 << (width - 1 - i)
    return res


def _get_crc_table(model: CrcModel) -> List[int]:
    """Generate or fetch cached 256-entry lookup table for a CRC model."""
    if model in _TABLE_CACHE:
        return _TABLE_CACHE[model]

    width = model.width
    poly = model.poly
    topbit = 1 << (width - 1)
    mask = (1 << width) - 1

    table = []
    if model.refin:
        ref_poly = reflect_bits(poly, width)
        for byte in range(256):
            cur = byte
            for _ in range(8):
                if cur & 1:
                    cur = (cur >> 1) ^ ref_poly
                else:
                    cur = cur >> 1
            table.append(cur & mask)
    else:
        for byte in range(256):
            cur = byte << (width - 8)
            for _ in range(8):
                if cur & topbit:
                    cur = ((cur << 1) ^ poly) & mask
                else:
                    cur = (cur << 1) & mask
            table.append(cur)

    _TABLE_CACHE[model] = table
    return table


def calculate_custom_crc(data: bytes, model: CrcModel) -> int:
    """Calculate CRC over data bytes using arbitrary Rocksoft Model parameters."""
    if not data:
        return 0

    width = model.width
    mask = (1 << width) - 1
    table = _get_crc_table(model)

    if model.refin:
        reg = reflect_bits(model.init, width)
        for byte in data:
            idx = (reg ^ byte) & 0xFF
            reg = ((reg >> 8) ^ table[idx]) & mask
        if not model.refout:
            reg = reflect_bits(reg, width)
    else:
        reg = model.init & mask
        shift = width - 8
        for byte in data:
            idx = ((reg >> shift) ^ byte) & 0xFF
            reg = ((reg << 8) ^ table[idx]) & mask
        if model.refout:
            reg = reflect_bits(reg, width)

    return (reg ^ model.xorout) & mask


def calculate_crc(
    data: bytes,
    algorithm: Union[CrcAlgorithm, str],
    custom_model: Optional[CrcModel] = None,
) -> int:
    """Calculate checksum or CRC over bytes using named preset or custom model."""
    if isinstance(algorithm, str):
        try:
            algo_enum = CrcAlgorithm(algorithm.lower())
        except ValueError:
            raise ValueError(f"Unsupported CRC algorithm: '{algorithm}'")
    else:
        algo_enum = algorithm

    if algo_enum == CrcAlgorithm.NONE:
        return 0

    if not data:
        return 0

    if algo_enum == CrcAlgorithm.SUM8:
        return sum(data) & 0xFF

    if algo_enum == CrcAlgorithm.SUM16:
        return sum(data) & 0xFFFF

    if algo_enum == CrcAlgorithm.XOR:
        res = 0
        for b in data:
            res ^= b
        return res & 0xFF

    if algo_enum == CrcAlgorithm.CUSTOM:
        if custom_model is None:
            raise ValueError("custom_model parameter must be provided when algorithm is 'custom'")
        return calculate_custom_crc(data, custom_model)

    if algo_enum in PRESET_MODELS:
        return calculate_custom_crc(data, PRESET_MODELS[algo_enum])

    raise ValueError(f"Unhandled CRC algorithm: {algo_enum}")


def format_crc_bytes(val: int, width: int, endian: str = "little") -> bytes:
    """Format an integer CRC value into raw bytes according to bit width and endianness."""
    byte_count = width // 8
    order = "<" if endian.lower() == "little" else ">"

    if byte_count == 1:
        return struct.pack("B", val & 0xFF)
    elif byte_count == 2:
        return struct.pack(f"{order}H", val & 0xFFFF)
    elif byte_count == 4:
        return struct.pack(f"{order}I", val & 0xFFFFFFFF)
    else:
        return val.to_bytes(byte_count, byteorder=endian.lower(), signed=False)


def parse_crc_bytes(raw: bytes, width: int, endian: str = "little") -> int:
    """Parse raw bytes into an integer CRC value according to bit width and endianness."""
    byte_count = width // 8
    if len(raw) < byte_count:
        raise ValueError(f"Expected at least {byte_count} bytes for {width}-bit CRC, got {len(raw)}")

    order = "<" if endian.lower() == "little" else ">"
    if byte_count == 1:
        return int(struct.unpack("B", raw[:1])[0])
    elif byte_count == 2:
        return int(struct.unpack(f"{order}H", raw[:2])[0])
    elif byte_count == 4:
        return int(struct.unpack(f"{order}I", raw[:4])[0])
    else:
        return int.from_bytes(raw[:byte_count], byteorder=endian.lower(), signed=False)


def verify_crc(
    data: bytes,
    expected_crc: int,
    algorithm: Union[CrcAlgorithm, str],
    custom_model: Optional[CrcModel] = None,
) -> bool:
    """Verify whether calculated CRC matches expected value."""
    actual = calculate_crc(data, algorithm, custom_model=custom_model)
    return actual == expected_crc
