"""Strongly-typed Pydantic v2 data models for protocol definitions and automation scripts."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from omniuart.core.crc import CrcModel

ALLOWED_BAUDRATES = {9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600}


class FieldType(str, Enum):
    """Supported primitive field data types."""

    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    BOOL = "bool"
    ENUM = "enum"
    STRING = "string"
    BYTES = "bytes"


class FramingType(str, Enum):
    """Protocol framing architecture."""

    BINARY = "binary"
    DELIMITED = "delimited"


class FieldSpec(BaseModel):
    """Specification for an individual payload or response field."""

    model_config = ConfigDict(extra="ignore")

    name: str
    type: FieldType
    endian: str = "little"
    default: Any = None
    min: Optional[float] = None
    max: Optional[float] = None
    unit: Optional[str] = None
    scale: Optional[float] = None
    options: Optional[Dict[Union[int, str], str]] = None
    length: Optional[int] = None

    @field_validator("endian")
    @classmethod
    def validate_endian(cls, v: str) -> str:
        low = v.lower()
        if low not in ("little", "big"):
            raise ValueError(f"Endian must be 'little' or 'big', got '{v}'")
        return low


class ResponseSpec(BaseModel):
    """Expected response structure corresponding to an outbound command."""

    model_config = ConfigDict(extra="ignore")

    id: Optional[Union[int, str]] = None
    timeout_ms: int = 1000
    fields: List[FieldSpec] = Field(default_factory=list)


class CommandSpec(BaseModel):
    """Definition of an outbound command and its parameter signature."""

    model_config = ConfigDict(extra="ignore")

    name: str
    id: Union[int, str]
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    parameters: List[FieldSpec] = Field(default_factory=list)
    response: Optional[ResponseSpec] = None


class TelemetrySpec(BaseModel):
    """Definition of an unsolicited broadcast or periodic sensor frame."""

    model_config = ConfigDict(extra="ignore")

    name: str
    id: Union[int, str]
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    fields: List[FieldSpec] = Field(default_factory=list)


class LengthSpec(BaseModel):
    """Dynamic frame length field configuration."""

    model_config = ConfigDict(extra="ignore")

    type: str = "uint16"
    endian: str = "little"
    includes: str = "payload_only"


class CommandIdSpec(BaseModel):
    """Opcode/Command ID field descriptor."""

    model_config = ConfigDict(extra="ignore")

    type: str = "uint8"
    endian: str = "little"


class IntegritySpec(BaseModel):
    """Checksum or CRC calculation specification."""

    model_config = ConfigDict(extra="ignore")

    algorithm: str
    width: Optional[int] = None
    poly: Optional[Union[int, str]] = None
    init: Optional[Union[int, str]] = None
    refin: bool = False
    refout: bool = False
    xorout: Optional[Union[int, str]] = 0
    endian: str = "little"
    check: Optional[Union[int, str]] = None

    def to_crc_model(self) -> Optional[CrcModel]:
        """Convert custom integrity parameters into a CrcModel instance."""
        if self.algorithm.lower() != "custom":
            return None

        if self.width is None or self.poly is None or self.init is None:
            raise ValueError("Custom CRC requires width, poly, and init to be defined.")

        def parse_hex_or_int(val: Union[int, str]) -> int:
            if isinstance(val, int):
                return val
            val_str = str(val).strip()
            return int(val_str, 16) if val_str.startswith(("0x", "0X")) else int(val_str)

        poly_int = parse_hex_or_int(self.poly)
        init_int = parse_hex_or_int(self.init)
        xorout_int = parse_hex_or_int(self.xorout) if self.xorout is not None else 0
        check_int = parse_hex_or_int(self.check) if self.check is not None else None

        return CrcModel(
            width=self.width,
            poly=poly_int,
            init=init_int,
            refin=self.refin,
            refout=self.refout,
            xorout=xorout_int,
            endian=self.endian,
            check=check_int,
        )


class FramingConfig(BaseModel):
    """Envelope framing parameters for binary or delimited stream protocols."""

    model_config = ConfigDict(extra="ignore")

    type: FramingType
    header: Optional[Union[List[int], str]] = None
    length: Optional[LengthSpec] = None
    command_id: Optional[CommandIdSpec] = None
    integrity: Optional[IntegritySpec] = None
    footer: Optional[Union[List[int], str]] = None
    prefix: Optional[str] = None
    delimiter: Optional[str] = None
    suffix: Optional[str] = None


class SerialConfig(BaseModel):
    """Default physical hardware serial communication settings."""

    model_config = ConfigDict(extra="ignore")

    baudrate: int
    bytesize: int = 8
    parity: str = "none"
    stopbits: float = 1
    flow_control: str = "none"
    timeout_ms: int = 1000

    @field_validator("baudrate")
    @classmethod
    def validate_baud(cls, v: int) -> int:
        if v not in ALLOWED_BAUDRATES:
            raise ValueError(f"Baudrate {v} not in standard set: {sorted(ALLOWED_BAUDRATES)}")
        return v


class ProtocolMeta(BaseModel):
    """Metadata block for a protocol definition."""

    model_config = ConfigDict(extra="ignore")

    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None


class ProtocolSpec(BaseModel):
    """Root model for an OmniUART protocol specification."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0.0"
    metadata: ProtocolMeta
    serial_config: SerialConfig
    framing: FramingConfig
    commands: List[CommandSpec] = Field(default_factory=list)
    telemetry: List[TelemetrySpec] = Field(default_factory=list)

    def get_command(self, name: str) -> Optional[CommandSpec]:
        """Lookup command by its human-readable identifier name."""
        for cmd in self.commands:
            if cmd.name == name:
                return cmd
        return None

    def get_command_by_id(self, cmd_id: Union[int, str]) -> Optional[CommandSpec]:
        """Lookup command by its numeric opcode or text ID."""
        for cmd in self.commands:
            if cmd.id == cmd_id:
                return cmd
        return None

    def get_telemetry_by_id(self, tel_id: Union[int, str]) -> Optional[TelemetrySpec]:
        """Lookup unsolicited telemetry frame by opcode."""
        for tel in self.telemetry:
            if tel.id == tel_id:
                return tel
        return None


class StepAssertion(BaseModel):
    """Condition asserted against response payload fields."""

    model_config = ConfigDict(extra="ignore")

    field: str
    op: str
    value: Any
    tolerance: Optional[float] = None


class ScriptStep(BaseModel):
    """Individual action step in an automated test sequence."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    command: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    expect_response: Optional[str] = None
    timeout_ms: Optional[int] = None
    delay_ms: Optional[int] = None
    log: Optional[str] = None
    assertions: List[StepAssertion] = Field(default_factory=list)


class ScriptConfig(BaseModel):
    """Global execution settings for an automated test script."""

    model_config = ConfigDict(extra="ignore")

    abort_on_error: bool = True
    default_timeout_ms: int = 1000
    inter_step_delay_ms: int = 0


class ScriptMeta(BaseModel):
    """Metadata block for an automation script."""

    model_config = ConfigDict(extra="ignore")

    name: str
    protocol: str
    description: Optional[str] = None
    author: Optional[str] = None


class ScriptSpec(BaseModel):
    """Root model for an OmniUART automated test script."""

    model_config = ConfigDict(extra="ignore")

    version: str = "1.0.0"
    meta: ScriptMeta
    config: ScriptConfig = Field(default_factory=ScriptConfig)
    steps: List[ScriptStep] = Field(default_factory=list)


def load_protocol(source: Union[str, Path]) -> ProtocolSpec:
    """Load and validate a ProtocolSpec from a file path or raw text string."""
    source_name = None
    if isinstance(source, Path):
        source_name = source.name
        raw = source.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) if source.suffix.lower() in (".yaml", ".yml") else json.loads(raw)
    elif isinstance(source, str) and "\n" not in source and Path(source).exists():
        path = Path(source)
        source_name = path.name
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) if path.suffix.lower() in (".yaml", ".yml") else json.loads(raw)
    else:
        raw_text = str(source)
        try:
            data = yaml.safe_load(raw_text)
        except Exception:
            data = json.loads(raw_text)

    if isinstance(data, dict) and ("physicalLayer" in data or "commandResponseModel" in data or "integrityCheck" in data):
        from omniuart.core.kit_adapter import parse_kit_protocol
        return parse_kit_protocol(data, source_name=source_name)

    return ProtocolSpec.model_validate(data)


def load_script(source: Union[str, Path]) -> ScriptSpec:
    """Load and validate a ScriptSpec from a file path or raw text string."""
    source_name = None
    if isinstance(source, Path):
        source_name = source.name
        raw = source.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) if source.suffix.lower() in (".yaml", ".yml") else json.loads(raw)
    elif isinstance(source, str) and "\n" not in source and Path(source).exists():
        path = Path(source)
        source_name = path.name
        raw = path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) if path.suffix.lower() in (".yaml", ".yml") else json.loads(raw)
    else:
        raw_text = str(source)
        try:
            data = yaml.safe_load(raw_text)
        except Exception:
            data = json.loads(raw_text)

    if isinstance(data, dict) and ("interfaceRef" in data or "onSequenceFailure" in data):
        from omniuart.core.sequence_adapter import parse_kit_sequence
        return parse_kit_sequence(data, source_name=source_name)

    return ScriptSpec.model_validate(data)

