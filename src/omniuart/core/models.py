"""Strongly-typed Pydantic v2 data models for protocol definitions and automation scripts."""

from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omniuart.core.limits import get_limits
from omniuart.core.crc import TRANSFORMS, CrcAlgorithm, CrcModel, resolve_algorithm

logger = logging.getLogger(__name__)

# Common rates for UI drop-downs and documentation. Any positive integer rate is valid; a rate outside
# this set only produces a warning (some hardware needs 250000 for DMX512, 76800, 1000000 and so on).
STANDARD_BAUDRATES = (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 250000, 460800, 921600)


class CommandSafety(str, Enum):
    """What a command can do to the device. Anything not declared is treated as ``mutating``.

    - ``read_only``: queries state, changes nothing. The only level that may run automatically
      (dashboard auto-run, auto-poll).
    - ``idempotent``: changes state, but sending it again has the same effect (set a value).
    - ``mutating``: changes state and is not safe to repeat.
    - ``destructive``: erases data, resets or reprograms the device.
    """

    READ_ONLY = "read_only"
    IDEMPOTENT = "idempotent"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"


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

    model_config = ConfigDict(extra="forbid")

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

    @field_validator("length")
    @classmethod
    def validate_length(cls, v: Optional[int]) -> Optional[int]:
        limit = get_limits().frame_bytes
        if v is not None and not 0 <= v <= limit:
            raise ValueError(f"field length {v} is outside 0..{limit} (OMNIUART_MAX_FRAME_BYTES)")
        return v


class ResponseSpec(BaseModel):
    """Expected response structure corresponding to an outbound command."""

    model_config = ConfigDict(extra="forbid")

    id: Optional[Union[int, str]] = None
    timeout_ms: int = 1000
    fields: List[FieldSpec] = Field(default_factory=list)


class CommandSpec(BaseModel):
    """Definition of an outbound command and its parameter signature."""

    model_config = ConfigDict(extra="forbid")

    name: str
    id: Union[int, str]
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    safety: CommandSafety = CommandSafety.MUTATING
    parameters: List[FieldSpec] = Field(default_factory=list)
    response: Optional[ResponseSpec] = None
    # Request parameters whose values must equal the same-named fields of the response (a transaction id,
    # sequence number or device address). A response that differs is not this command's answer.
    correlate: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_correlation_fields(self) -> "CommandSpec":
        if self.correlate:
            if self.response is None:
                raise ValueError(f"command '{self.name}' sets correlate but defines no response")
            params = {p.name for p in self.parameters}
            replies = {f.name for f in self.response.fields}
            for name in self.correlate:
                if name not in params or name not in replies:
                    raise ValueError(f"command '{self.name}': correlate field '{name}' must be both a parameter and a response field")
        return self

    @property
    def is_read_only(self) -> bool:
        return self.safety is CommandSafety.READ_ONLY

    @property
    def needs_confirmation(self) -> bool:
        """Whether a front end must get an explicit yes before sending (mutating and destructive commands)."""
        return self.safety in (CommandSafety.MUTATING, CommandSafety.DESTRUCTIVE)


class TelemetrySpec(BaseModel):
    """Definition of an unsolicited broadcast or periodic sensor frame."""

    model_config = ConfigDict(extra="forbid")

    name: str
    id: Union[int, str]
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    fields: List[FieldSpec] = Field(default_factory=list)


class LengthSpec(BaseModel):
    """Dynamic frame length field configuration."""

    model_config = ConfigDict(extra="forbid")

    type: str = "uint16"
    endian: str = "little"
    includes: str = "payload_only"


class CommandIdSpec(BaseModel):
    """Opcode/Command ID field descriptor."""

    model_config = ConfigDict(extra="forbid")

    type: str = "uint8"
    endian: str = "little"


class IntegritySpec(BaseModel):
    """Checksum or CRC calculation specification."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str
    width: Optional[int] = None
    poly: Optional[Union[int, str]] = None
    init: Optional[Union[int, str]] = None
    refin: bool = False
    refout: bool = False
    xorout: Optional[Union[int, str]] = 0
    endian: str = "little"
    check: Optional[Union[int, str]] = None
    covers: str = "after_header"
    transform: str = "none"  # final transform of a checksum: none, twos_complement, ones_complement
    carry_wrap: bool = False  # end-around-carry summation for sum8 (LIN enhanced checksum)

    @field_validator("transform")
    @classmethod
    def validate_transform(cls, v: str) -> str:
        if v not in TRANSFORMS:
            raise ValueError(f"transform must be one of {', '.join(TRANSFORMS)}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_runtime(self) -> "IntegritySpec":
        """Fail at load time when the algorithm is unknown or a custom model is incomplete or inconsistent."""
        algo = resolve_algorithm(self.algorithm)
        if algo is CrcAlgorithm.CUSTOM:
            self.to_crc_model()
        return self

    @field_validator("covers")
    @classmethod
    def validate_covers(cls, v: str) -> str:
        if v not in ("after_header", "full_frame", "payload_only"):
            raise ValueError(f"covers must be 'after_header', 'full_frame' or 'payload_only', got '{v}'")
        return v

    def to_crc_model(self) -> Optional[CrcModel]:
        """Convert custom integrity parameters into a CrcModel instance."""
        if resolve_algorithm(self.algorithm) is not CrcAlgorithm.CUSTOM:
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

    model_config = ConfigDict(extra="forbid")

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

    model_config = ConfigDict(extra="forbid")

    baudrate: int
    bytesize: int = 8
    parity: str = "none"
    stopbits: float = 1
    flow_control: str = "none"
    timeout_ms: int = 1000

    @field_validator("baudrate")
    @classmethod
    def validate_baud(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"Baudrate must be a positive integer, got {v}")
        if v not in STANDARD_BAUDRATES:
            logger.warning("Non-standard baud rate %d: check that the hardware supports it", v)
        return v


class ProtocolMeta(BaseModel):
    """Metadata block for a protocol definition."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    description: Optional[str] = None
    author: Optional[str] = None


class ProtocolSpec(BaseModel):
    """Root model for an OmniUART protocol specification."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0.0"
    metadata: ProtocolMeta
    serial_config: SerialConfig
    framing: FramingConfig
    commands: List[CommandSpec] = Field(default_factory=list)
    telemetry: List[TelemetrySpec] = Field(default_factory=list)
    # Default ``correlate`` for every command that has all of these as both a parameter and a response field.
    correlate: List[str] = Field(default_factory=list)

    def correlation_fields(self, cmd: CommandSpec) -> List[str]:
        """The fields that must match between ``cmd``'s request and a response for it to be accepted."""
        if cmd.correlate:
            return list(cmd.correlate)
        if not self.correlate or cmd.response is None:
            return []
        params = {p.name for p in cmd.parameters}
        replies = {f.name for f in cmd.response.fields}
        return list(self.correlate) if all(n in params and n in replies for n in self.correlate) else []

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

    model_config = ConfigDict(extra="forbid")

    field: str
    op: str
    value: Any
    tolerance: Optional[float] = None


class ScriptStep(BaseModel):
    """Individual action step in an automated test sequence."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = None
    command: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    expect_response: Optional[str] = None
    timeout_ms: Optional[int] = None
    delay_ms: Optional[int] = None
    log: Optional[str] = None
    assertions: List[StepAssertion] = Field(default_factory=list)
    save: Dict[str, str] = Field(default_factory=dict)


class ScriptConfig(BaseModel):
    """Global execution settings for an automated test script."""

    model_config = ConfigDict(extra="forbid")

    abort_on_error: bool = True
    default_timeout_ms: int = 1000
    inter_step_delay_ms: int = 0


class ScriptMeta(BaseModel):
    """Metadata block for an automation script."""

    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: str
    description: Optional[str] = None
    author: Optional[str] = None


class ScriptSpec(BaseModel):
    """Root model for an OmniUART automated test script."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0.0"
    meta: ScriptMeta
    config: ScriptConfig = Field(default_factory=ScriptConfig)
    variables: Dict[str, Any] = Field(default_factory=dict)
    steps: List[ScriptStep] = Field(default_factory=list)


def _is_existing_file(text: str) -> bool:
    """True if ``text`` names an existing file. Long inline documents are not valid paths (OSError)."""
    try:
        return "\n" not in text and Path(text).exists()
    except (OSError, ValueError):
        return False


def _check_definition_size(size: int, what: str) -> None:
    limit = get_limits().definition_bytes
    if size > limit:
        raise ValueError(f"{what} is {size} bytes, over the {limit}-byte limit (OMNIUART_MAX_DEFINITION_BYTES)")


def _read_limited(path: Path) -> str:
    _check_definition_size(path.stat().st_size, f"'{path.name}'")
    return path.read_text(encoding="utf-8")


def _parse_document(raw: str, is_yaml: bool) -> Any:
    """Parse YAML or JSON; a document nested too deeply to parse is a ``ValueError``, not a crash."""
    try:
        return yaml.safe_load(raw) if is_yaml else json.loads(raw)
    except RecursionError:
        raise ValueError("definition is nested too deeply to parse") from None
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse definition: {exc}") from exc


def _is_path_like(source: Union[str, Path]) -> bool:
    """True if ``source`` looks like a file path rather than raw inline YAML/JSON content."""
    if isinstance(source, Path):
        return True
    if not isinstance(source, str) or "\n" in source or "\r" in source:
        return False
    s = source.strip()
    if s.endswith((".yaml", ".yml", ".json")) or "/" in s or "\\" in s or s.startswith((".", "..")):
        return True
    return False


def _load_definition_data(source: Union[str, Path]) -> tuple[Any, Optional[str]]:
    """Helper to read and parse raw document data from file path or text string."""
    source_name = None
    if isinstance(source, Path) or _is_path_like(source) or _is_existing_file(str(source)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Protocol or script file not found: {source}")
        source_name = path.name
        raw = _read_limited(path)
        data = _parse_document(raw, path.suffix.lower() in (".yaml", ".yml"))
    else:
        raw_text = str(source)
        _check_definition_size(len(raw_text.encode("utf-8")), "definition text")
        try:
            data = _parse_document(raw_text, True)
        except ValueError:
            data = _parse_document(raw_text, False)
    return data, source_name


def load_protocol_file(path: Union[str, Path]) -> ProtocolSpec:
    """Load ProtocolSpec explicitly from a file path, raising FileNotFoundError if missing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Protocol file not found: {path}")
    return load_protocol(p)


def load_protocol_text(text: str) -> ProtocolSpec:
    """Load ProtocolSpec explicitly from raw YAML or JSON text."""
    _check_definition_size(len(text.encode("utf-8")), "definition text")
    try:
        data = _parse_document(text, True)
    except ValueError:
        data = _parse_document(text, False)
    if isinstance(data, dict) and ("physicalLayer" in data or "commandResponseModel" in data or "integrityCheck" in data):
        from omniuart.core.kit_adapter import parse_kit_protocol
        return parse_kit_protocol(data, source_name=None)
    return ProtocolSpec.model_validate(data)


def load_protocol(source: Union[str, Path]) -> ProtocolSpec:
    """Load and validate a ProtocolSpec from a file path or raw text string."""
    data, source_name = _load_definition_data(source)

    if isinstance(data, dict) and ("physicalLayer" in data or "commandResponseModel" in data or "integrityCheck" in data):
        from omniuart.core.kit_adapter import parse_kit_protocol
        return parse_kit_protocol(data, source_name=source_name)

    return ProtocolSpec.model_validate(data)


def load_script_file(path: Union[str, Path]) -> ScriptSpec:
    """Load ScriptSpec explicitly from a file path, raising FileNotFoundError if missing."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Script file not found: {path}")
    return load_script(p)


def load_script_text(text: str) -> ScriptSpec:
    """Load ScriptSpec explicitly from raw YAML or JSON text."""
    _check_definition_size(len(text.encode("utf-8")), "definition text")
    try:
        data = _parse_document(text, True)
    except ValueError:
        data = _parse_document(text, False)
    if isinstance(data, dict) and ("interfaceRef" in data or "onSequenceFailure" in data):
        from omniuart.core.sequence_adapter import parse_kit_sequence
        return parse_kit_sequence(data, source_name=None)

    script = ScriptSpec.model_validate(data)
    max_steps = get_limits().script_steps
    if len(script.steps) > max_steps:
        raise ValueError(f"script has {len(script.steps)} steps, over the limit of {max_steps} (OMNIUART_MAX_SCRIPT_STEPS)")
    return script


def load_script(source: Union[str, Path]) -> ScriptSpec:
    """Load and validate a ScriptSpec from a file path or raw text string."""
    data, source_name = _load_definition_data(source)

    if isinstance(data, dict) and ("interfaceRef" in data or "onSequenceFailure" in data):
        from omniuart.core.sequence_adapter import parse_kit_sequence
        return parse_kit_sequence(data, source_name=source_name)

    script = ScriptSpec.model_validate(data)
    max_steps = get_limits().script_steps
    if len(script.steps) > max_steps:
        raise ValueError(f"script has {len(script.steps)} steps, over the limit of {max_steps} (OMNIUART_MAX_SCRIPT_STEPS)")
    return script

