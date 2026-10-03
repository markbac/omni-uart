"""Zero-dependency CRC and Checksum Calculation Engine.

Supports standard industrial presets (CRC-8 SMBus, CRC-16 Modbus, CRC-16 CCITT,
CRC-32 IEEE 802.3, Sum8, Sum16, XOR) as well as arbitrary custom parametric CRCs
defined according to the Rocksoft Parameter Model.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Literal, Optional, Union


class CrcAlgorithm(str, Enum):
    """Enumeration of supported standard CRC presets."""

    NONE = "none"
    SUM8 = "sum8"
    SUM16 = "sum16"
    XOR = "xor"
    FLETCHER16 = "fletcher16"
    CRC8 = "crc8"
    CRC16_MODBUS = "crc16_modbus"
    CRC16_CCITT = "crc16_ccitt"
    CRC16_CCITT_FALSE = "crc16_ccitt_false"
    CRC16_ARC = "crc16_arc"
    CRC16_DNP = "crc16_dnp"
    CRC32 = "crc32"
    CUSTOM = "custom"


_ALIASES = {
    "checksum8": "sum8",
    "sum_8": "sum8",
    "checksum_8": "sum8",
    "checksum16": "sum16",
    "sum_16": "sum16",
    "checksum_16": "sum16",
    "xor8": "xor",
    "xor_8": "xor",
    "fletcher_16": "fletcher16",
}

TRANSFORMS = ("none", "twos_complement", "ones_complement")


def byte_order(endian: str) -> Literal["little", "big"]:
    """``"little"`` or ``"big"`` (case-insensitive); any other value raises ``ValueError``."""
    value = endian.lower()
    if value == "little":
        return "little"
    if value == "big":
        return "big"
    raise ValueError(f"Endianness must be 'little' or 'big', got {endian!r}")


def normalize_algorithm_name(name: str) -> str:
    """Canonical lower-case name: ``crc-16-modbus`` -> ``crc16_modbus``, ``checksum-8`` -> ``sum8``, ``xor-8`` -> ``xor``."""
    key = re.sub(r"[\s-]+", "_", str(name).strip().lower())
    key = re.sub(r"^crc_(\d+)", r"crc\1", key)
    return _ALIASES.get(key, key)


def resolve_algorithm(name: Union["CrcAlgorithm", str]) -> "CrcAlgorithm":
    """Look up an algorithm by any accepted spelling; raises ``ValueError`` listing the supported names."""
    if isinstance(name, CrcAlgorithm):
        return name
    try:
        return CrcAlgorithm(normalize_algorithm_name(name))
    except ValueError:
        supported = ", ".join(a.value for a in CrcAlgorithm)
        raise ValueError(f"Unsupported CRC algorithm: '{name}' (supported: {supported})") from None


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
        if not isinstance(self.width, int) or self.width < 8 or self.width > 64 or self.width % 8:
            raise ValueError(f"CRC width must be a multiple of 8 between 8 and 64 bits, got {self.width!r}")
        if self.endian not in ("little", "big"):
            raise ValueError(f"Endianness must be 'little' or 'big', got '{self.endian}'")
        mask = (1 << self.width) - 1
        for name in ("poly", "init", "xorout"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"CRC {name} must be an integer, got {value!r}")
            if not 0 <= value <= mask:
                raise ValueError(f"CRC {name} 0x{value:X} does not fit in {self.width} bits")
        if self.poly == 0:
            raise ValueError("CRC polynomial must be non-zero")
        if not isinstance(self.refin, bool) or not isinstance(self.refout, bool):
            raise ValueError("CRC refin and refout must be booleans")
        if self.check is not None:
            if not isinstance(self.check, int) or not 0 <= self.check <= mask:
                raise ValueError(f"CRC check {self.check!r} does not fit in {self.width} bits")
            computed = calculate_custom_crc(CHECK_INPUT, self)
            if computed != self.check:
                raise ValueError(
                    f"CRC model check value mismatch: declared 0x{self.check:0{self.width // 4}X}, "
                    f"computed 0x{computed:0{self.width // 4}X} for b'123456789'"
                )


CHECK_INPUT = b"123456789"

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
    """Calculate CRC over data bytes using arbitrary Rocksoft Model parameters.

    Empty input is not special: the result follows from ``init``, reflection and ``xorout``.
    """
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


def _fletcher16(data: bytes) -> int:
    sum1 = sum2 = 0
    for byte in data:
        sum1 = (sum1 + byte) % 255
        sum2 = (sum2 + sum1) % 255
    return (sum2 << 8) | sum1


def _carry_wrapped_sum8(data: bytes) -> int:
    """Sum with the carry added back in (end-around carry), as used by LIN's enhanced checksum."""
    total = 0
    for byte in data:
        total += byte
        if total > 0xFF:
            total -= 0xFF
    return total


def apply_transform(value: int, width: int, transform: str) -> int:
    """Final transform applied to a checksum: none, twos_complement or ones_complement."""
    mask = (1 << width) - 1
    if transform == "none":
        return value & mask
    if transform == "ones_complement":
        return (~value) & mask
    if transform == "twos_complement":
        return (-value) & mask
    raise ValueError(f"Unknown checksum transform '{transform}' (expected one of {', '.join(TRANSFORMS)})")


def calculate_crc(
    data: bytes,
    algorithm: Union[CrcAlgorithm, str],
    custom_model: Optional[CrcModel] = None,
    transform: str = "none",
    carry_wrap: bool = False,
) -> int:
    """Calculate a checksum or CRC over ``data`` using a named preset or a custom model.

    ``transform`` (checksums only) applies a final one's or two's complement and ``carry_wrap`` selects
    end-around-carry summation for ``sum8``. Empty input is calculated like any other input.
    """
    algo = resolve_algorithm(algorithm)
    if transform not in TRANSFORMS:
        raise ValueError(f"Unknown checksum transform '{transform}' (expected one of {', '.join(TRANSFORMS)})")

    if algo is CrcAlgorithm.NONE:
        return 0
    if algo is CrcAlgorithm.SUM8:
        raw = _carry_wrapped_sum8(data) if carry_wrap else sum(data) & 0xFF
        return apply_transform(raw, 8, transform)
    if algo is CrcAlgorithm.SUM16:
        return apply_transform(sum(data) & 0xFFFF, 16, transform)
    if algo is CrcAlgorithm.XOR:
        res = 0
        for b in data:
            res ^= b
        return apply_transform(res, 8, transform)
    if algo is CrcAlgorithm.FLETCHER16:
        return _fletcher16(data)
    if algo is CrcAlgorithm.CUSTOM:
        if custom_model is None:
            raise ValueError("custom_model parameter must be provided when algorithm is 'custom'")
        return calculate_custom_crc(data, custom_model)
    if algo in PRESET_MODELS:
        return calculate_custom_crc(data, PRESET_MODELS[algo])
    raise ValueError(f"Unhandled CRC algorithm: {algo}")


def algorithm_width(algorithm: Union[CrcAlgorithm, str], custom_model: Optional[CrcModel] = None) -> int:
    """Width in bits of the integrity field the algorithm produces (0 for ``none``)."""
    algo = resolve_algorithm(algorithm)
    if algo is CrcAlgorithm.NONE:
        return 0
    if algo is CrcAlgorithm.CUSTOM:
        if custom_model is None:
            raise ValueError("custom_model parameter must be provided when algorithm is 'custom'")
        return custom_model.width
    if algo in PRESET_MODELS:
        return PRESET_MODELS[algo].width
    return {CrcAlgorithm.SUM8: 8, CrcAlgorithm.XOR: 8, CrcAlgorithm.SUM16: 16, CrcAlgorithm.FLETCHER16: 16}[algo]


# Standard named presets. Each model is verified against its published check value on import.
PRESET_MODELS: Dict[CrcAlgorithm, CrcModel] = {
    CrcAlgorithm.CRC8: CrcModel(width=8, poly=0x07, init=0x00, refin=False, refout=False, xorout=0x00, endian="big", check=0xF4),
    CrcAlgorithm.CRC16_MODBUS: CrcModel(width=16, poly=0x8005, init=0xFFFF, refin=True, refout=True, xorout=0x0000, endian="little", check=0x4B37),
    CrcAlgorithm.CRC16_CCITT: CrcModel(width=16, poly=0x1021, init=0xFFFF, refin=False, refout=False, xorout=0x0000, endian="big", check=0x29B1),
    CrcAlgorithm.CRC16_CCITT_FALSE: CrcModel(width=16, poly=0x1021, init=0xFFFF, refin=False, refout=False, xorout=0x0000, endian="big", check=0x29B1),
    CrcAlgorithm.CRC16_ARC: CrcModel(width=16, poly=0x8005, init=0x0000, refin=True, refout=True, xorout=0x0000, endian="little", check=0xBB3D),
    CrcAlgorithm.CRC16_DNP: CrcModel(width=16, poly=0x3D65, init=0x0000, refin=True, refout=True, xorout=0xFFFF, endian="little", check=0xEA82),
    CrcAlgorithm.CRC32: CrcModel(width=32, poly=0x04C11DB7, init=0xFFFFFFFF, refin=True, refout=True, xorout=0xFFFFFFFF, endian="little", check=0xCBF43926),
}


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
        return val.to_bytes(byte_count, byteorder=byte_order(endian), signed=False)


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
        return int.from_bytes(raw[:byte_count], byteorder=byte_order(endian), signed=False)


def verify_crc(
    data: bytes,
    expected_crc: int,
    algorithm: Union[CrcAlgorithm, str],
    custom_model: Optional[CrcModel] = None,
) -> bool:
    """Verify whether calculated CRC matches expected value."""
    actual = calculate_crc(data, algorithm, custom_model=custom_model)
    return actual == expected_crc
