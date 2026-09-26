"""Unit tests for kit_adapter parsing uart-interface-schema-kit protocol specifications."""

from pathlib import Path
import pytest

from omniuart.core.models import ProtocolSpec, load_protocol
from omniuart.core.kit_adapter import load_kit_protocol

KIT_EXAMPLES_DIR = Path("../uart-interface-schema-kit/kit/examples")


def test_load_all_kit_examples_except_g460() -> None:
    """Verify that all kit protocol examples load successfully into ProtocolSpec except g460."""
    if not KIT_EXAMPLES_DIR.exists():
        pytest.skip("KIT_EXAMPLES_DIR directory not present on runner")
    json_files = list(KIT_EXAMPLES_DIR.glob("*.json"))
    assert len(json_files) >= 25, "Expected at least 25 kit example protocol files"

    loaded_count = 0
    for file_path in json_files:
        if "g460" in file_path.name.lower():
            # Must be excluded and raise ValueError
            with pytest.raises(ValueError, match="G460 protocol is explicitly excluded"):
                load_protocol(file_path)
        else:
            proto = load_protocol(file_path)
            assert isinstance(proto, ProtocolSpec)
            assert proto.metadata.name
            assert proto.serial_config.baudrate > 0
            assert len(proto.commands) >= 1
            loaded_count += 1

    assert loaded_count >= 28, f"Expected at least 28 valid kit protocols, loaded {loaded_count}"


def test_g460_explicit_exclusion_rejection() -> None:
    """Verify that G460 protocol files are explicitly rejected when loading."""
    g460_path = KIT_EXAMPLES_DIR / "g460-uart-interface.json"
    if g460_path.exists():
        with pytest.raises(ValueError, match="G460 protocol is explicitly excluded"):
            load_kit_protocol(g460_path)
