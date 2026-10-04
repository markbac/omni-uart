"""Core protocol engine, framing codec, integrity algorithms, and catalog manager."""

from omniuart.core.catalog import CatalogManager
from omniuart.core.crc import CrcModel
from omniuart.core.kit_adapter import parse_kit_protocol
from omniuart.core.models import ProtocolSpec, ScriptSpec, load_protocol, load_script
from omniuart.core.sequence_adapter import parse_kit_sequence
from omniuart.core.session import DeviceSession, SerialSession, SessionState, SessionStatistics

__all__ = [
    "CatalogManager",
    "CrcModel",
    "DeviceSession",
    "ProtocolSpec",
    "ScriptSpec",
    "SerialSession",
    "SessionState",
    "SessionStatistics",
    "load_protocol",
    "load_script",
    "parse_kit_protocol",
    "parse_kit_sequence",
]

