"""Regression tests for the desktop/CLI frame builder (#255)."""

import pytest

pytest.importorskip("tkinter")

from pathlib import Path  # noqa: E402

from omniuart.core.catalog import CatalogManager  # noqa: E402
from omniuart.core.codec import CodecError  # noqa: E402
from omniuart.core.crc import calculate_crc  # noqa: E402
from omniuart.core.models import load_protocol  # noqa: E402
from omniuart.core.codec import build_frame_payload  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "protocols"


@pytest.fixture()
def sensor():
    return load_protocol(EXAMPLES / "binary_sensor_node.yaml")


def test_builder_writes_the_declared_crc_not_a_byte_sum(sensor):
    frame = build_frame_payload(sensor, sensor.get_command("get_readings"), {"channel": 1})
    assert frame[6:8] == calculate_crc(frame[2:6], "crc16_modbus").to_bytes(2, "little")


def test_builder_rejects_out_of_range_values(sensor):
    with pytest.raises(CodecError):
        build_frame_payload(sensor, sensor.get_command("get_readings"), {"channel": 99})


def test_builder_rejects_unparseable_values(sensor):
    with pytest.raises(CodecError):
        build_frame_payload(sensor, sensor.get_command("get_readings"), {"channel": "abc"})


def test_builder_accepts_gui_string_values(sensor):
    assert build_frame_payload(sensor, sensor.get_command("get_readings"), {"channel": "2"})[5] == 2


def test_kit_at_command_builds_the_line_the_modem_expects():
    spec = CatalogManager().get_protocol("at-commands-uart-interface.json")
    assert spec is not None
    assert build_frame_payload(spec, spec.get_command("AttentionCheck"), {}) == b"AT\r\n"
