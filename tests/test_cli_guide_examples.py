"""Unit test verifying CLI examples documented in docs/cli-guide.md (#227, #321)."""

from pathlib import Path
import shlex
from omniuart.cli import build_parser, main


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


def test_all_documented_cli_guide_commands_parse():
    guide_path = Path(__file__).resolve().parents[1] / "docs" / "cli-guide.md"
    content = guide_path.read_text(encoding="utf-8")
    parser = build_parser()

    tested = 0
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("omniuart "):
            tokens = shlex.split(line)[1:]
            parsed = parser.parse_args(tokens)
            assert parsed.subcommand is not None
            tested += 1

    assert tested >= 19
