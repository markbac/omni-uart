"""Baud rate handling is not limited to a fixed set and is never silently replaced (#258)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from omniuart.core.kit_adapter import parse_kit_protocol
from omniuart.core.models import STANDARD_BAUDRATES, SerialConfig, load_protocol

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "protocols"


@pytest.mark.parametrize("rate", [1200, 2400, 4800, 76800, 250000, 1000000])
def test_any_positive_rate_is_accepted(rate: int) -> None:
    assert SerialConfig(baudrate=rate).baudrate == rate


def test_non_standard_rate_warns_but_standard_does_not(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        SerialConfig(baudrate=115200)
        assert not caplog.records
        SerialConfig(baudrate=76800)
    assert "Non-standard baud rate 76800" in caplog.text


@pytest.mark.parametrize("rate", [0, -9600])
def test_non_positive_rate_is_rejected(rate: int) -> None:
    with pytest.raises(ValidationError):
        SerialConfig(baudrate=rate)


def _kit(baud: object) -> dict:
    return {"protocolName": "T", "version": "1.0", "physicalLayer": {"baudRate": baud}, "commands": []}


@pytest.mark.parametrize(
    "declared, expected",
    [(250000, 250000), (4800, 4800), ("2400", 2400), (9600.0, 9600), ([76800, 115200], 76800), (1000000, 1000000)],
)
def test_kit_adapter_keeps_the_declared_rate(declared: object, expected: int) -> None:
    assert parse_kit_protocol(_kit(declared), source_name="t").serial_config.baudrate == expected


@pytest.mark.parametrize("declared", ["fast", True, -1, 0, 9600.5, [], None])
def test_kit_adapter_rejects_instead_of_substituting(declared: object) -> None:
    with pytest.raises(ValueError, match="baudRate"):
        parse_kit_protocol(_kit(declared), source_name="t")


@pytest.mark.parametrize("name, rate", [("dmx512-uart-interface.json", 250000), ("nmea0183-uart-interface.json", 4800)])
def test_bundled_examples_load_at_their_real_rate(name: str, rate: int) -> None:
    path = EXAMPLES / name
    if not path.exists():
        pytest.skip("example not present")
    assert load_protocol(path).serial_config.baudrate == rate


def test_standard_rate_list_is_a_single_shared_constant() -> None:
    assert 250000 in STANDARD_BAUDRATES and 115200 in STANDARD_BAUDRATES
