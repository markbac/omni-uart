"""Helpers shared by the protocol conformance suite and the golden-vector generator."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import FrameCodec
from omniuart.core.models import CommandSpec, FieldSpec, FieldType, ProtocolSpec

logging.disable(logging.WARNING)  # the kit adapter warns about every unsupported feature; the suite is about behaviour


def sample_value(f: FieldSpec, which: str = "default") -> Any:
    """A valid value for field ``f``: ``default`` (its default, else the lowest valid), ``min`` or ``max``."""
    t = f.type
    if t is FieldType.BOOL:
        return bool(f.default) if which == "default" and f.default is not None else which == "max"
    if t is FieldType.ENUM:
        keys = list(f.options or {0: ""})
        value = f.default if which == "default" and f.default is not None else (keys[-1] if which == "max" else keys[0])
        return value
    if t is FieldType.STRING:
        return str(f.default) if which == "default" and f.default is not None else "A" * min(f.length or 1, 4)
    if t is FieldType.BYTES:
        if f.default is not None and which == "default":
            return f.default
        return b"\x01" * min(f.length or 1, 4)
    bits = {"8": 8, "16": 16, "32": 32, "64": 64}.get(t.value.lstrip("uintfloa"), 0)
    if t in (FieldType.FLOAT32, FieldType.FLOAT64):
        lo, hi = (f.min if f.min is not None else 0.0), (f.max if f.max is not None else 1.0)
    elif t.value.startswith("uint"):
        lo, hi = (f.min if f.min is not None else 0), (f.max if f.max is not None else (1 << bits) - 1)
    else:
        lo, hi = (f.min if f.min is not None else -(1 << (bits - 1))), (f.max if f.max is not None else (1 << (bits - 1)) - 1)
    if which == "default" and f.default is not None:
        return f.default
    return hi if which == "max" else lo if which == "min" else max(lo, min(hi, 0 if t.value.startswith(("int", "float")) else lo))


def sample_params(cmd: CommandSpec, which: str = "default") -> Dict[str, Any]:
    return {p.name: sample_value(p, which) for p in cmd.parameters}


def catalog_protocols() -> List[Tuple[str, ProtocolSpec]]:
    catalog = CatalogManager()
    out = []
    for path in catalog.list_protocol_files():
        spec = catalog.get_protocol(path.name)
        if spec is not None:
            out.append((path.name, spec))
    return out


def command_cases() -> Iterator[Tuple[str, ProtocolSpec, CommandSpec]]:
    for name, spec in catalog_protocols():
        for cmd in spec.commands:
            yield name, spec, cmd


def encode_request(spec: ProtocolSpec, cmd: CommandSpec, params: Optional[Dict[str, Any]] = None) -> bytes:
    return FrameCodec(spec).encode_command(cmd, sample_params(cmd) if params is None else params)


# Commands the suite cannot yet verify because of a documented gap in how a kit definition is mapped, not
# because of a codec bug. They are expected failures (strict), so fixing the gap turns them into a failure
# of this table that must then be deleted.
AT_SHARED_ID_GAP = "delimited commands that share an id (or an id prefix) and differ only by parameters cannot be told apart when decoding"
WIDE_ID_GAP = "the kit command id does not fit the one-byte command_id the adapter assumes"
KIT_FRAMING_GAP = "kit framing (syncBytes, lengthField, escaping) is not mapped by the kit adapter, so the frame is not self-delimiting"
KNOWN_GAPS: Dict[Tuple[str, str], str] = {
    ("at-commands-uart-interface.json", "SetOperatorManual"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "SetOperatorFormatOnly"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "SetOperatorManualAutomatic"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "EnterPukWithNewPin"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "LockFacility"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "QueryFacilityLock"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "QcfgSetDataInactTimer"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "QcfgGpioInitialize"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "QcfgGpioQuery"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "QcfgGpioConfigure"): AT_SHARED_ID_GAP,
    ("at-commands-uart-interface.json", "EnterDataMode"): AT_SHARED_ID_GAP,
    ("autobaud-bootloader-uart-interface.json", "WriteMemory"): KIT_FRAMING_GAP,
    ("bacnet-mstp-uart-interface.json", "DataFrame"): KIT_FRAMING_GAP,
    ("dmx512-uart-interface.json", "ChannelFrame"): KIT_FRAMING_GAP,
    ("dnp3-uart-interface.json", "DataLinkFrame"): KIT_FRAMING_GAP,
    ("hci-h4-uart-interface.json", "HCI_Set_AFH_Host_Channel_Classification"): WIDE_ID_GAP,
    ("hci-h4-uart-interface.json", "HCI_ACL_Data"): KIT_FRAMING_GAP,
    ("mavlink-ftp-uart-interface.json", "FTP_OpenFileRO"): KIT_FRAMING_GAP,
    ("multidrop-9bit-uart-interface.json", "SlaveMessage"): KIT_FRAMING_GAP,
    ("ubx-uart-interface.json", "CFG-PRT-SetBaud"): KIT_FRAMING_GAP,
    ("ubx-uart-interface.json", "NAV-PVT"): KIT_FRAMING_GAP,
    ("ubx-uart-interface.json", "NAV-STATUS"): KIT_FRAMING_GAP,
    ("xbee-api-uart-interface.json", "SetChannelATCommand"): KIT_FRAMING_GAP,
    ("xbee-api-uart-interface.json", "TransmitRequest"): KIT_FRAMING_GAP,
}
