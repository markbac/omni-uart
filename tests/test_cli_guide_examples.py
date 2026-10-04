"""Unit test verifying CLI examples documented in docs/cli-guide.md (#227)."""

import json
from omniuart.cli import main


def test_cli_list_command(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Discovered Protocols" in out


def test_cli_info_command(capsys):
    assert main(["info", "binary_sensor_node"]) == 0
    out = capsys.readouterr().out
    assert "PROTOCOL HELP: BinarySensorNode" in out


def test_cli_send_virtual_command(capsys):
    assert main(["send", "binary_sensor_node", "ping", "--virtual"]) == 0
    out = capsys.readouterr().out
    assert "Response  :" in out


def test_cli_lint_command(capsys):
    assert main(["lint", "examples/protocols/binary_sensor_node.yaml"]) == 0
    out = capsys.readouterr().out
    assert "VALID" in out


def test_cli_generate_c_header(capsys):
    assert main(["generate", "c", "binary_sensor_node"]) == 0
    out = capsys.readouterr().out
    assert "BINARYSENSORNODE_H" in out
