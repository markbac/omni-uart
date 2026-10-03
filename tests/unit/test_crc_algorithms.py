"""CRC algorithms, empty-input semantics, model validation and bundled-example coverage (#204, #205, #260, #261)."""

from __future__ import annotations

from pathlib import Path

import pytest

from omniuart.core.crc import (
    CrcAlgorithm,
    CrcModel,
    algorithm_width,
    calculate_crc,
    normalize_algorithm_name,
    resolve_algorithm,
)
from omniuart.core.models import IntegritySpec, load_protocol
from omniuart.linter import lint_protocol_file

CHECK = b"123456789"
EXAMPLES = sorted((Path(__file__).resolve().parents[2] / "examples" / "protocols").glob("*.*"))


@pytest.mark.parametrize(
    "algorithm, expected",
    [
        ("crc8", 0xF4),
        ("crc16_modbus", 0x4B37),
        ("crc16_ccitt", 0x29B1),
        ("crc16_ccitt_false", 0x29B1),
        ("crc16_arc", 0xBB3D),
        ("crc16_dnp", 0xEA82),
        ("crc32", 0xCBF43926),
        ("fletcher16", 0x1EDE),
        ("sum8", sum(CHECK) & 0xFF),
        ("sum16", sum(CHECK)),
        ("xor", 0x31),
    ],
)
def test_golden_vector_for_123456789(algorithm: str, expected: int) -> None:
    assert calculate_crc(CHECK, algorithm) == expected


@pytest.mark.parametrize(
    "algorithm, expected",
    [
        ("crc8", 0x00),
        ("crc16_modbus", 0xFFFF),
        ("crc16_ccitt", 0xFFFF),
        ("crc16_ccitt_false", 0xFFFF),
        ("crc16_arc", 0x0000),
        ("crc16_dnp", 0xFFFF),
        ("crc32", 0x00000000),
        ("fletcher16", 0),
        ("sum8", 0),
        ("xor", 0),
        ("none", 0),
    ],
)
def test_empty_input_follows_the_model_not_a_blanket_zero(algorithm: str, expected: int) -> None:
    assert calculate_crc(b"", algorithm) == expected


def test_custom_model_empty_input_uses_init_and_xorout() -> None:
    model = CrcModel(width=16, poly=0x1021, init=0xABCD, xorout=0x00FF)
    assert calculate_crc(b"", "custom", model) == 0xABCD ^ 0x00FF
    reflected = CrcModel(width=16, poly=0x1021, init=0x0001, refin=True, refout=True)
    assert calculate_crc(b"", "custom", reflected) == 0x8000


@pytest.mark.parametrize(
    "spelling, canonical",
    [
        ("crc-16-modbus", "crc16_modbus"),
        ("CRC_16_CCITT_FALSE", "crc16_ccitt_false"),
        ("crc-16-dnp", "crc16_dnp"),
        ("crc-16-arc", "crc16_arc"),
        ("crc-8", "crc8"),
        ("crc-32", "crc32"),
        ("checksum-8", "sum8"),
        ("xor-8", "xor"),
        ("xor8", "xor"),
        ("fletcher-16", "fletcher16"),
    ],
)
def test_kit_and_legacy_spellings_resolve(spelling: str, canonical: str) -> None:
    assert normalize_algorithm_name(spelling) == canonical
    assert resolve_algorithm(spelling) is CrcAlgorithm(canonical)


def test_unknown_algorithm_names_the_supported_ones() -> None:
    with pytest.raises(ValueError, match="Unsupported CRC algorithm.*crc16_modbus"):
        calculate_crc(b"x", "crc-99-bogus")


def test_checksum_transforms_and_carry_wrap() -> None:
    assert calculate_crc(b"\x01\x02\x03", "sum8") == 6
    assert calculate_crc(b"\x01\x02\x03", "sum8", transform="twos_complement") == 0xFA
    assert calculate_crc(b"\x01\x02\x03", "sum8", transform="ones_complement") == 0xF9
    assert calculate_crc(b"\xff\x01", "sum8") == 0
    assert calculate_crc(b"\xff\x01", "sum8", carry_wrap=True) == 1
    with pytest.raises(ValueError, match="transform"):
        calculate_crc(b"x", "sum8", transform="negate")


def test_algorithm_widths() -> None:
    assert [algorithm_width(a) for a in ("none", "sum8", "xor", "crc8", "fletcher16", "crc16_dnp", "crc32")] == [0, 8, 8, 8, 16, 16, 32]


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"width": 12, "poly": 0x80F, "init": 0}, "multiple of 8"),
        ({"width": 0, "poly": 1, "init": 0}, "multiple of 8"),
        ({"width": 72, "poly": 1, "init": 0}, "multiple of 8"),
        ({"width": 8, "poly": 0x107, "init": 0}, "poly 0x107 does not fit in 8 bits"),
        ({"width": 16, "poly": 0x1021, "init": 0x10000}, "init 0x10000 does not fit"),
        ({"width": 16, "poly": 0x1021, "init": 0, "xorout": -1}, "xorout"),
        ({"width": 16, "poly": 0, "init": 0}, "non-zero"),
        ({"width": 16, "poly": "0x1021", "init": 0}, "poly must be an integer"),
        ({"width": 16, "poly": 0x1021, "init": 0, "endian": "middle"}, "Endianness"),
        ({"width": 16, "poly": 0x1021, "init": 0, "refin": 1}, "booleans"),
        ({"width": 16, "poly": 0x1021, "init": 0xFFFF, "check": 0x1234}, "check value mismatch"),
        ({"width": 16, "poly": 0x1021, "init": 0xFFFF, "check": 0x1FFFF}, "check"),
    ],
)
def test_impossible_models_are_rejected_with_useful_errors(kwargs: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        CrcModel(**kwargs)


@pytest.mark.parametrize("width, poly, init", [(8, 0x07, 0), (16, 0x1021, 0xFFFF), (24, 0x864CFB, 0xB704CE), (32, 0x04C11DB7, 0xFFFFFFFF), (64, 0x42F0E1EBA9EA3693, 0)])
def test_common_widths_are_supported(width: int, poly: int, init: int) -> None:
    model = CrcModel(width=width, poly=poly, init=init)
    assert 0 <= calculate_crc(CHECK, "custom", model) < (1 << width)


def test_crc24_openpgp_and_crc64_ecma_match_published_check_values() -> None:
    assert calculate_crc(CHECK, "custom", CrcModel(width=24, poly=0x864CFB, init=0xB704CE)) == 0x21CF02
    assert calculate_crc(CHECK, "custom", CrcModel(width=64, poly=0x42F0E1EBA9EA3693, init=0)) == 0x6C40DF5F0B497347


def test_integrity_spec_rejects_unknown_algorithm_and_incomplete_custom_model_at_load() -> None:
    with pytest.raises(ValueError, match="Unsupported CRC algorithm"):
        IntegritySpec(algorithm="crc-99-bogus")
    with pytest.raises(ValueError, match="width, poly, and init"):
        IntegritySpec(algorithm="custom", width=16)
    with pytest.raises(ValueError, match="transform"):
        IntegritySpec(algorithm="sum8", transform="negate")


def test_lint_fails_on_an_unknown_algorithm(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "meta: {name: Bad, version: '1.0', description: x}\n"
        "serial_config: {baudrate: 9600}\n"
        "framing: {type: binary, header: [170], integrity: {algorithm: crc-99-bogus}}\n"
        "commands: []\n",
        encoding="utf-8",
    )
    valid, errors = lint_protocol_file(bad)
    assert not valid and any("Unsupported CRC algorithm" in e for e in errors)


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_bundled_example_can_compute_its_own_integrity_field(path: Path) -> None:
    spec = load_protocol(path)
    integrity = spec.framing.integrity
    if integrity is None:
        return
    value = calculate_crc(CHECK, integrity.algorithm, integrity.to_crc_model(), integrity.transform, integrity.carry_wrap)
    width = algorithm_width(integrity.algorithm, integrity.to_crc_model())
    assert 0 <= value < (1 << width) if width else value == 0


def test_kit_custom_parameters_and_coverage_are_read() -> None:
    path = next(p for p in EXAMPLES if p.name == "mavlink-v1-uart-interface.json")
    integrity = load_protocol(path).framing.integrity
    assert integrity is not None and integrity.algorithm == "custom"
    assert (integrity.width, integrity.refin, integrity.refout) == (16, True, True)
    assert integrity.covers == "after_header"  # length-to-payload-inclusive
    assert calculate_crc(CHECK, "custom", integrity.to_crc_model()) == 0x6F91  # CRC-16/MCRF4XX


@pytest.mark.parametrize(
    "name, transform, carry",
    [("j1708-uart-interface.json", "twos_complement", False), ("lin-uart-interface.json", "ones_complement", True), ("xbee-api-uart-interface.json", "ones_complement", False)],
)
def test_kit_checksum_transform_and_summation_mode_are_read(name: str, transform: str, carry: bool) -> None:
    integrity = load_protocol(next(p for p in EXAMPLES if p.name == name)).framing.integrity
    assert integrity is not None
    assert (integrity.transform, integrity.carry_wrap) == (transform, carry)
