"""Exact-byte tests for the AT modem and Modbus RTU simulators (no substring matching)."""

from __future__ import annotations

import pytest
from omniuart.core.crc import calculate_crc
from omniuart.core.simulator import ATModemSimulator, ModbusRtuSimulator


def feed(sim, data: bytes):
    return sim.process_incoming_bytes(bytearray(data))


def test_at_answers_once_for_crlf_terminator() -> None:
    assert feed(ATModemSimulator(), b"AT\r\n") == b"\r\nOK\r\n"


def test_at_lf_only_and_cr_only_terminators() -> None:
    assert feed(ATModemSimulator(), b"AT\n") == b"\r\nOK\r\n"
    assert feed(ATModemSimulator(), b"AT\r") == b"\r\nOK\r\n"


def test_at_unknown_command_is_error() -> None:
    assert feed(ATModemSimulator(), b"AT+FOOBAR\r\n") == b"\r\nERROR\r\n"


def test_at_information_response_framing() -> None:
    assert feed(ATModemSimulator(), b"AT+CSQ\r\n") == b"\r\n+CSQ: 24,99\r\n\r\nOK\r\n"


def test_at_partial_command_waits_and_pipelined_commands_both_answered() -> None:
    sim, buf = ATModemSimulator(), bytearray(b"AT+CS")
    assert sim.process_incoming_bytes(buf) is None and bytes(buf) == b"AT+CS"
    assert feed(sim, b"AT\r\nAT+FOO\r\n") == b"\r\nOK\r\n\r\nERROR\r\n"


def test_at_blank_lines_produce_no_response() -> None:
    assert feed(ATModemSimulator(), b"\r\n\r\n") is None


def request(addr: int, func: int, reg: int, count: int, corrupt: bool = False) -> bytes:
    body = bytes([addr, func]) + reg.to_bytes(2, "big") + count.to_bytes(2, "big")
    crc = calculate_crc(body, "crc16_modbus") ^ (1 if corrupt else 0)
    return body + crc.to_bytes(2, "little")


def with_crc(body: bytes) -> bytes:
    return body + calculate_crc(body, "crc16_modbus").to_bytes(2, "little")


def test_modbus_read_registers_exact() -> None:
    resp = feed(ModbusRtuSimulator(), request(1, 3, 0, 2))
    assert resp == with_crc(bytes([1, 3, 4]) + (1234).to_bytes(2, "big") + (5678).to_bytes(2, "big"))


def test_modbus_bad_crc_is_ignored() -> None:
    assert feed(ModbusRtuSimulator(), request(1, 3, 0, 2, corrupt=True)) is None


def test_modbus_wrong_address_is_ignored_and_consumed() -> None:
    sim, buf = ModbusRtuSimulator(), bytearray(request(2, 3, 0, 1))
    assert sim.process_incoming_bytes(buf) is None and not buf


@pytest.mark.parametrize("count", [0, 126, 200, 65535])
def test_modbus_bad_count_is_illegal_data_value(count: int) -> None:
    assert feed(ModbusRtuSimulator(), request(1, 3, 0, count)) == with_crc(bytes([1, 0x83, 0x03]))


def test_modbus_address_overflow_is_illegal_data_address() -> None:
    assert feed(ModbusRtuSimulator(), request(1, 3, 0xFFFF, 2)) == with_crc(bytes([1, 0x83, 0x02]))


def test_modbus_unsupported_function_is_illegal_function() -> None:
    assert feed(ModbusRtuSimulator(), request(1, 6, 0, 1)) == with_crc(bytes([1, 0x86, 0x01]))
