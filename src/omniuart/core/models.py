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

    # Binary protocol extension attributes (#199)
    bit_width: Optional[int] = None
    offset: Optional[int] = None
    length_ref: Optional[str] = None
    count_ref: Optional[str] = None
    condition: Optional[str] = None
    discriminator: Optional[str] = None
    discriminator_value: Optional[Any] = None
    is_array: bool = False
    item_type: Optional[FieldType] = None
    nested_fields: Optional[List[FieldSpec]] = None
    encoding: Optional[str] = None
    offset_val: Optional[float] = None
    expression: Optional[str] = None
    # A constant: always sent with this value and never supplied by the caller. Leading fixed
    # parameters tell apart commands that share a command id (for example a data item id).
    fixed: Optional[Any] = None

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
    # Text protocols only: regular expressions searched in the reply (multiline). A reply matching any
    # error pattern, or not matching the success pattern, fails the exchange as an invalid response.
    success_pattern: Optional[str] = None
    error_patterns: List[str] = Field(default_factory=list)


class CommandSpec(BaseModel):
    """Definition of an outbound command and its parameter signature."""

    model_config = ConfigDict(extra="forbid")

    name: str
    id: Union[int, str]
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    safety: CommandSafety = CommandSafety.MUTATING
    safety_reason: Optional[str] = None
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


class ErrorReplySpec(BaseModel):
    """A reply id the device sends instead of a response when it refuses or fails a command (a NAK)."""

    model_config = ConfigDict(extra="forbid")

    id: Union[int, str]
    name: str
    description: Optional[str] = None


class LengthSpec(BaseModel):
    """Dynamic frame length field configuration."""

    model_config = ConfigDict(extra="forbid")

    type: str = "uint16"
    endian: str = "little"
    # What the length value counts: payload_only, payload_and_cmd (command id + payload),
    # full_frame (header to footer), or length_to_end (from the length field itself to the end of the frame).
    includes: str = "payload_only"

    @field_validator("includes")
    @classmethod
    def validate_includes(cls, v: str) -> str:
        allowed = ("payload_only", "payload_and_cmd", "full_frame", "length_to_end")
        if v not in allowed:
            raise ValueError(f"length.includes must be one of {', '.join(allowed)}")
        return v


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
            crc_model = self.to_crc_model()
            if crc_model and crc_model.check is not None:
                from omniuart.core.crc import calculate_custom_crc
                calculated_check = calculate_custom_crc(b"123456789", crc_model)
                if calculated_check != crc_model.check:
                    raise ValueError(
                        f"Custom CRC check vector validation failed: calculated 0x{calculated_check:X}, declared check 0x{crc_model.check:X}"
                    )
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
    rs485_rts_mode: bool = False
    rs485_turnaround_ms: float = 0.0
    pulse_pins: List[Dict[str, Any]] = Field(default_factory=list)

    @field_validator("baudrate")
    @classmethod
    def validate_baud(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"Baudrate must be a positive integer, got {v}")
        if v not in STANDARD_BAUDRATES:
            logger.warning("Non-standard baud rate %d: check that the hardware supports it", v)
        return v


MULTIPART_ROLES = (
    "packet_number",  # sequence number of the packet, starting at ``first_packet_number``
    "packet_count",  # number of packets in the whole message
    "message_id",  # identifies the message; the same in every packet of one message
    "total_length",  # length in bytes of the whole (reassembled) data
    "data_length",  # length in bytes of this packet's data section
    "message_crc",  # CRC of the whole data, with ``message_crc`` parameters
    "packet_crc",  # CRC of this packet's data section, with ``packet_crc`` parameters
    "running_crc",  # CRC of all data up to and including this packet, with ``message_crc`` parameters
    "data",  # this packet's data section
)


class MultipartPacketLayouts(BaseModel):
    """The packet body of the first packet and of every following packet of a multipart message."""

    model_config = ConfigDict(extra="forbid")

    first: List[FieldSpec]
    next: Optional[List[FieldSpec]] = None  # defaults to ``first``

    def layout(self, index: int) -> List[FieldSpec]:
        """The fields of packet ``index`` (0 = first packet)."""
        return self.first if index == 0 or self.next is None else self.next


class MultipartWriteSpec(MultipartPacketLayouts):
    """Host-to-device: a write command whose ``packet_param`` carries one packet body per frame.

    Every packet is a separate request; its successful response acknowledges it. A NAK (a declared
    error reply) or a failed response stops the write with an error.
    """

    commands: List[str]
    packet_param: str = "packet"


class MultipartReadSpec(MultipartPacketLayouts):
    """Device-to-host: a read command answered with one packet body per reply in ``packet_field``.

    The host sends the read command once per packet. When ``packet_param`` is set, that request
    parameter carries a request body built from ``request_first`` / ``request_next`` (for example
    the packet number being asked for).
    """

    commands: List[str]
    packet_field: str = "packet"
    packet_param: Optional[str] = None
    request_first: Optional[List[FieldSpec]] = None
    request_next: Optional[List[FieldSpec]] = None

    def request_layout(self, index: int) -> Optional[List[FieldSpec]]:
        if index == 0 or self.request_next is None:
            return self.request_first
        return self.request_next


class MultipartSpec(BaseModel):
    """Items larger than one frame, split across several frames of the same command (#347).

    The packet layouts are ordinary field lists. A field's meaning comes from ``roles`` (role ->
    field name); a field named like a role takes that role without being listed. Fields with no role
    are sent with their ``fixed`` or ``default`` value (an obsolete field sent as zero) and ignored
    when received.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: Optional[str] = None
    # The logical name of the whole value in ``send``/``run`` parameters and the API.
    value_param: str = "data"
    max_data_per_packet: int = Field(gt=0)
    first_packet_number: int = 0
    retries: int = Field(default=0, ge=0)
    roles: Dict[str, str] = Field(default_factory=dict)
    message_crc: Optional[IntegritySpec] = None
    packet_crc: Optional[IntegritySpec] = None
    write: Optional[MultipartWriteSpec] = None
    read: Optional[MultipartReadSpec] = None

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: Dict[str, str]) -> Dict[str, str]:
        unknown = sorted(set(v) - set(MULTIPART_ROLES))
        if unknown:
            raise ValueError(f"unknown multipart role(s) {', '.join(unknown)}; roles are {', '.join(MULTIPART_ROLES)}")
        return v

    def field_for(self, role: str) -> str:
        """The field name that carries ``role``."""
        return self.roles.get(role, role)

    def role_of(self, field_name: str) -> Optional[str]:
        """The role a field carries, or ``None`` for a plain (reserved or constant) field."""
        for role in MULTIPART_ROLES:
            if self.field_for(role) == field_name:
                return role
        return None

    @model_validator(mode="after")
    def _check_layouts(self) -> "MultipartSpec":
        if self.write is None and self.read is None:
            raise ValueError(f"multipart '{self.name}' defines neither write nor read")
        crc_roles = {"message_crc": self.message_crc, "running_crc": self.message_crc, "packet_crc": self.packet_crc}
        layouts: List[tuple[str, List[FieldSpec]]] = []
        for direction, part in (("write", self.write), ("read", self.read)):
            if part is None:
                continue
            layouts.append((f"{direction}.first", part.first))
            if part.next is not None:
                layouts.append((f"{direction}.next", part.next))
        for where, fields in layouts:
            by_name = {f.name: f for f in fields}
            data_field = by_name.get(self.field_for("data"))
            if data_field is None:
                raise ValueError(f"multipart '{self.name}' {where} has no '{self.field_for('data')}' (data) field")
            if data_field.type is not FieldType.BYTES:
                raise ValueError(f"multipart '{self.name}' {where}: the data field must be of type bytes")
            if where == "read.first" and self.field_for("total_length") not in by_name:
                raise ValueError(f"multipart '{self.name}' read.first must carry the total length (a '{self.field_for('total_length')}' field)")
            for f in fields:
                role = self.role_of(f.name)
                if role in crc_roles and crc_roles[role] is None:
                    param = "message_crc" if role in ("message_crc", "running_crc") else "packet_crc"
                    raise ValueError(f"multipart '{self.name}' {where} has a {role} field but no '{param}' CRC parameters")
        return self


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
    # Replies that report a failure instead of answering: an exchange that gets one ends as ``device_error``.
    error_replies: List[ErrorReplySpec] = Field(default_factory=list)
    # Default ``correlate`` for every command that has all of these as both a parameter and a response field.
    correlate: List[str] = Field(default_factory=list)
    # Items larger than one frame, carried as a sequence of packets of the same command (#347).
    multipart: List[MultipartSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_multipart(self) -> "ProtocolSpec":
        seen: Dict[str, str] = {}
        for mp in self.multipart:
            for direction, part in (("write", mp.write), ("read", mp.read)):
                if part is None:
                    continue
                for name in part.commands:
                    cmd = self.get_command(name)
                    if cmd is None:
                        raise ValueError(f"multipart '{mp.name}' {direction} command '{name}' is not defined")
                    if name in seen:
                        raise ValueError(f"command '{name}' is used by multipart '{seen[name]}' and '{mp.name}'")
                    seen[name] = mp.name
                    if cmd.response is None:
                        raise ValueError(f"multipart '{mp.name}' {direction} command '{name}' defines no response")
                    params = {p.name: p for p in cmd.parameters}
                    replies = {f.name: f for f in cmd.response.fields}
                    carrier = {
                        "write": params.get(getattr(part, "packet_param", "")),
                        "read": replies.get(getattr(part, "packet_field", "")),
                    }[direction]
                    if carrier is not None and carrier.type is not FieldType.BYTES:
                        raise ValueError(f"multipart {direction} command '{name}': the packet field '{carrier.name}' must be of type bytes")
                    if direction == "write":
                        assert isinstance(part, MultipartWriteSpec)
                        if part.packet_param not in params:
                            raise ValueError(f"multipart write command '{name}' has no '{part.packet_param}' parameter for the packet")
                    else:
                        assert isinstance(part, MultipartReadSpec)
                        if part.packet_field not in replies:
                            raise ValueError(f"multipart read command '{name}' has no '{part.packet_field}' response field for the packet")
                        if part.packet_param is not None and part.packet_param not in params:
                            raise ValueError(f"multipart read command '{name}' has no '{part.packet_param}' parameter for the request")
        return self

    def multipart_for(self, cmd: Union[str, CommandSpec]) -> Optional[tuple[MultipartSpec, str]]:
        """The multipart definition a command uses and its direction (``write`` or ``read``), if any."""
        name = cmd.name if isinstance(cmd, CommandSpec) else cmd
        for mp in self.multipart:
            if mp.write is not None and name in mp.write.commands:
                return mp, "write"
            if mp.read is not None and name in mp.read.commands:
                return mp, "read"
        return None

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
    if isinstance(data, dict) and "asyncapi" in data:
        from omniuart.core.asyncapi_importer import load_asyncapi_protocol
        return load_asyncapi_protocol(data, source_name=None)
    return ProtocolSpec.model_validate(data)


def load_protocol(source: Union[str, Path]) -> ProtocolSpec:
    """Load and validate a ProtocolSpec from a file path or raw text string."""
    data, source_name = _load_definition_data(source)

    if isinstance(data, dict) and ("physicalLayer" in data or "commandResponseModel" in data or "integrityCheck" in data):
        from omniuart.core.kit_adapter import parse_kit_protocol
        return parse_kit_protocol(data, source_name=source_name)
    if isinstance(data, dict) and "asyncapi" in data:
        # An AsyncAPI document with x-omniuart extensions is a protocol source too (#346).
        from omniuart.core.asyncapi_importer import load_asyncapi_protocol
        return load_asyncapi_protocol(data, source_name=source_name)

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

