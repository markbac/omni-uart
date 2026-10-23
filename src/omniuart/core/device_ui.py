"""Declarative Device UI Schema Subsystem for OmniUART (#229).

Defines a declarative Device UI Schema separate from protocol framing, describing device identity,
capabilities, controls, telemetry, navigation, safety rules, grouping, and widget presentation hints.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
import yaml

from omniuart.core.codec import DecodedFrame
from omniuart.core.models import CommandSafety, FieldSpec, ProtocolSpec

logger = logging.getLogger(__name__)


class DeviceIdentity(BaseModel):
    """Device identity metadata."""

    name: str
    model: str = "Generic Device"
    vendor: Optional[str] = None
    version: str = "1.0.0"
    description: Optional[str] = None
    icon: Optional[str] = "device"


class WidgetSpec(BaseModel):
    """Declarative UI control, telemetry widget, or transfer control element (#229, #246)."""

    widget_type: str = Field(description="Widget type: slider, switch, button, dropdown, gauge, line_plot, badge, text, file_transfer, firmware_update")
    field_ref: Optional[str] = Field(default=None, description="Mapped protocol field or command parameter")
    label: str
    icon: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    unit: Optional[str] = None
    options: Optional[Dict[Any, str]] = None
    presentation_hints: Dict[str, Any] = Field(default_factory=dict)
    supported_file_types: Optional[List[str]] = Field(default=None, description="Allowed file extensions e.g. ['.bin', '.hex', '.json']")
    max_size_bytes: Optional[int] = Field(default=None, description="Max allowed file size in bytes")
    transfer_type: Optional[str] = Field(default=None, description="Transfer semantic type: firmware, configuration, certificate, log, binary")
    destructive: bool = Field(default=False, description="Flag indicating destructive or device-changing operation requiring confirmation")
    confirm_prompt: Optional[str] = Field(default=None, description="Confirmation prompt displayed before executing transfer")
    safety_warning: Optional[str] = Field(default=None, description="Detailed hazard warning for dangerous device operations")


class GroupSpec(BaseModel):
    """Group container organizing widgets into logical sections."""

    name: str
    title: str
    icon: Optional[str] = None
    layout: str = "grid"  # grid, vertical, horizontal
    widgets: List[WidgetSpec] = Field(default_factory=list)


class PanelSpec(BaseModel):
    """Navigation panel or tab organizing groups."""

    name: str
    title: str
    icon: Optional[str] = None
    groups: List[GroupSpec] = Field(default_factory=list)


class SafetyRuleSpec(BaseModel):
    """Safety and confirmation rule for high-risk operations."""

    command: str
    require_confirmation: bool = True
    warning_message: Optional[str] = None
    danger_zone: bool = False



class UIMode(str, Enum):
    """Three presentation modes for Device Control Console (#235)."""

    OPERATOR = "operator"    # Simple, safe, task-oriented controls and status
    ENGINEER = "engineer"    # Decoded messages, timing, protocol diagnostics
    DEVELOPER = "developer"  # Raw frames/hex, session internals, low-level debugging


class TransferProtocolSpec(BaseModel):
    """How a device's protocol carries a file transfer, attached to the Device UI Schema (#251).

    Each phase names a protocol command. Chunks are sent one at a time: the chunk command's successful
    response (or, when ``ack_command`` is set, that command's successful response) acknowledges the
    chunk, and a failed one is retried up to ``retries`` times. A transfer counts as installed only when
    the device answers ``commit_command`` successfully; without a commit command it is reported as
    transferred but not committed.
    """

    start_command: Optional[str] = None
    chunk_command: str = "transfer_data"
    ack_command: Optional[str] = None
    commit_command: Optional[str] = None
    abort_command: Optional[str] = None
    default_chunk_size: int = Field(default=256, gt=0)
    max_chunk_size: int = Field(default=4096, gt=0)
    retries: int = Field(default=3, ge=0)
    # Logical transfer value -> the protocol parameter that carries it. A value is sent only to a
    # command that has that parameter.
    params: Dict[str, str] = Field(
        default_factory=lambda: {
            "file_name": "file_name",
            "file_type": "file_type",
            "total_size": "total_size",
            "checksum": "checksum",
            "chunk_size": "chunk_size",
            "sequence": "sequence",
            "offset": "offset",
            "data": "data",
            "chunk_crc32": "chunk_crc32",
            "is_last": "is_last",
        }
    )

    def commands(self) -> Dict[str, str]:
        """Phase -> command name, for every phase that is configured."""
        named = {
            "start": self.start_command,
            "chunk": self.chunk_command,
            "ack": self.ack_command,
            "commit": self.commit_command,
            "abort": self.abort_command,
        }
        return {phase: name for phase, name in named.items() if name}


class DeviceUISpec(BaseModel):
    """Declarative Device UI Specification model (#229, #235, #242, #251)."""

    schema_version: str = "1.0.0"
    revision: int = 1
    theme: str = "modern"
    compatible_protocol_version: Optional[str] = None
    identity: DeviceIdentity
    protocol_ref: str
    panels: List[PanelSpec] = Field(default_factory=list)
    safety_rules: List[SafetyRuleSpec] = Field(default_factory=list)
    transfer_protocol: Optional[TransferProtocolSpec] = None
    supported_modes: List[UIMode] = Field(
        default_factory=lambda: [UIMode.OPERATOR, UIMode.ENGINEER, UIMode.DEVELOPER]
    )


class DeviceUICompatibilityReport(BaseModel):
    """Compatibility report between a DeviceUISpec and a ProtocolSpec (#242)."""

    is_compatible: bool
    schema_version_compatible: bool = True
    protocol_version_matches: bool = True
    missing_commands: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    missing_telemetry: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


def check_protocol_compatibility(
    ui_spec: DeviceUISpec,
    protocol_spec: ProtocolSpec,
) -> DeviceUICompatibilityReport:
    """Validate compatibility between a DeviceUISpec and a ProtocolSpec (#242).

    Checks:
    - Protocol reference match.
    - Protocol version compatibility.
    - Bound fields exist in protocol parameters or telemetry.
    - Bound commands in buttons, transfers, and safety rules exist in protocol.
    """
    errors: List[str] = []
    warnings: List[str] = []
    missing_commands: List[str] = []
    missing_fields: List[str] = []
    missing_telemetry: List[str] = []

    # Check protocol reference
    if ui_spec.protocol_ref and ui_spec.protocol_ref.lower() != protocol_spec.metadata.name.lower():
        warnings.append(
            f"Device UI protocol_ref '{ui_spec.protocol_ref}' differs from protocol name '{protocol_spec.metadata.name}'"
        )

    # Check protocol version compatibility
    protocol_version_matches = True
    if ui_spec.compatible_protocol_version:
        if ui_spec.compatible_protocol_version != protocol_spec.metadata.version:
            protocol_version_matches = False
            warnings.append(
                f"Protocol version '{protocol_spec.metadata.version}' does not match UI compatible version '{ui_spec.compatible_protocol_version}'"
            )

    cmd_map = {cmd.name: cmd for cmd in protocol_spec.commands}
    all_param_names = {p.name for cmd in protocol_spec.commands for p in cmd.parameters}
    all_telemetry_fields = {f.name for tel in protocol_spec.telemetry for f in tel.fields}

    # Validate the transfer definition (#251)
    if ui_spec.transfer_protocol is not None:
        for phase, name in ui_spec.transfer_protocol.commands().items():
            if name not in cmd_map:
                missing_commands.append(name)
                errors.append(f"Transfer {phase} command '{name}' does not exist in the protocol")

    # Validate safety rules
    for rule in ui_spec.safety_rules:
        if rule.command not in cmd_map:
            missing_commands.append(rule.command)
            errors.append(f"Safety rule references non-existent command '{rule.command}'")

    # Validate widgets in panels
    for panel in ui_spec.panels:
        for group in panel.groups:
            for widget in group.widgets:
                if not widget.field_ref:
                    continue

                ref = widget.field_ref
                # Check if it's a command reference (button, transfer, or command-level widget)
                if widget.widget_type in ("button", "file_transfer", "firmware_update"):
                    if ref not in cmd_map:
                        missing_commands.append(ref)
                        errors.append(f"Widget '{widget.label}' references non-existent command '{ref}'")
                    continue

                # Check if dotted: cmd.param
                if "." in ref:
                    cmd_part, param_part = ref.split(".", 1)
                    if cmd_part in cmd_map:
                        cmd_params = {p.name for p in cmd_map[cmd_part].parameters}
                        if param_part not in cmd_params:
                            missing_fields.append(ref)
                            errors.append(f"Widget '{widget.label}' references unknown parameter '{param_part}' on command '{cmd_part}'")
                    else:
                        missing_commands.append(cmd_part)
                        errors.append(f"Widget '{widget.label}' references parameter on unknown command '{cmd_part}'")
                    continue

                # Plain field reference: check parameter names, telemetry fields, or command names
                if ref not in all_param_names and ref not in all_telemetry_fields and ref not in cmd_map:
                    if group.name == "telemetry":
                        missing_telemetry.append(ref)
                    else:
                        missing_fields.append(ref)
                    errors.append(f"Widget '{widget.label}' references unknown field '{ref}'")

    is_compatible = len(errors) == 0

    return DeviceUICompatibilityReport(
        is_compatible=is_compatible,
        schema_version_compatible=True,
        protocol_version_matches=protocol_version_matches,
        missing_commands=sorted(set(missing_commands)),
        missing_fields=sorted(set(missing_fields)),
        missing_telemetry=sorted(set(missing_telemetry)),
        warnings=warnings,
        errors=errors,
    )


def migrate_ui_spec(data: Dict[str, Any], target_version: str = "1.0.0") -> DeviceUISpec:
    """Migrate a raw or legacy Device UI definition dictionary to target schema version (#242)."""
    migrated = dict(data)

    # Legacy identity: string to dict
    if isinstance(migrated.get("identity"), str):
        migrated["identity"] = {"name": migrated["identity"], "model": "Migrated Device"}
    elif not migrated.get("identity"):
        name = migrated.get("protocol_ref") or migrated.get("protocol") or "Device"
        migrated["identity"] = {"name": name, "model": "Migrated Device"}

    # Legacy protocol -> protocol_ref
    if "protocol" in migrated and "protocol_ref" not in migrated:
        migrated["protocol_ref"] = migrated.pop("protocol")
    elif "protocol_ref" not in migrated:
        migrated["protocol_ref"] = migrated.get("identity", {}).get("name", "generic_protocol")

    # Legacy sections/controls -> panels/groups
    if "panels" not in migrated:
        groups: List[Dict[str, Any]] = []
        if "sections" in migrated and isinstance(migrated["sections"], list):
            for sec in migrated.pop("sections"):
                if isinstance(sec, dict):
                    widgets = sec.get("widgets", [])
                    groups.append({
                        "name": sec.get("name", "section"),
                        "title": sec.get("title", "Section"),
                        "layout": sec.get("layout", "grid"),
                        "widgets": widgets,
                    })
        elif "controls" in migrated and isinstance(migrated["controls"], list):
            controls = migrated.pop("controls")
            groups.append({
                "name": "controls",
                "title": "Controls",
                "layout": "grid",
                "widgets": controls,
            })
        migrated["panels"] = [{"name": "main", "title": "Main Workspace", "groups": groups}]

    migrated["schema_version"] = target_version
    return DeviceUISpec.model_validate(migrated)


def export_device_ui(spec: DeviceUISpec, format: str = "yaml") -> str:
    """Export DeviceUISpec definition to YAML or JSON string (#242)."""
    fmt = format.lower().strip()
    if fmt in ("json", "js"):
        return spec.model_dump_json(indent=2)
    elif fmt in ("yaml", "yml"):
        data = spec.model_dump(mode="json")
        return yaml.safe_dump(data, sort_keys=False)
    else:
        raise ValueError(f"Unsupported export format '{format}'. Use 'yaml' or 'json'.")


def import_device_ui(content: str, format: Optional[str] = None) -> DeviceUISpec:
    """Import and validate a DeviceUISpec definition from YAML or JSON string (#242)."""
    stripped = content.strip()
    if not stripped:
        raise ValueError("Cannot import empty UI specification")

    if (format and format.lower() == "json") or stripped.startswith("{"):
        import json
        data = json.loads(stripped)
    else:
        data = yaml.safe_load(stripped)

    if not isinstance(data, dict):
        raise ValueError("UI specification content must be a JSON/YAML mapping object")

    return migrate_ui_spec(data)


def _safe_name(text: str) -> str:
    """Reduce ``text`` to a file-name stem of letters, digits, ``-`` and ``_``."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip().lower()).strip("_")
    return cleaned or "device"


class DeviceUIStore:
    """Storage repository for persisting, versioning, and managing Device UI definitions (#242)."""

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None) -> None:
        if storage_dir is None:
            self.storage_dir = Path(".omniuart") / "ui"
        else:
            self.storage_dir = Path(storage_dir)

    def save(
        self,
        spec: DeviceUISpec,
        filename: Optional[str] = None,
        format: str = "yaml",
    ) -> Path:
        """Persist a DeviceUISpec to disk (#242).

        Saving changed content over an existing definition archives the old file under ``history/`` and
        stores the new one with the next revision number, so every saved revision can be reproduced.
        """
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        ext = "json" if format.lower() == "json" else "yaml"
        if not filename:
            filename = f"{_safe_name(spec.protocol_ref)}_ui.{ext}"
        target = self._resolve(filename)

        if target.is_file():
            previous = import_device_ui(target.read_text(encoding="utf-8"))
            if previous.model_dump(exclude={"revision"}) == spec.model_dump(exclude={"revision"}):
                return target
            history = self.storage_dir / "history"
            history.mkdir(exist_ok=True)
            target.replace(history / f"{target.stem}.r{previous.revision}{target.suffix}")
            spec = spec.model_copy(update={"revision": max(spec.revision, previous.revision + 1)})

        target.write_text(export_device_ui(spec, format=format), encoding="utf-8")
        return target

    def history(self, filename: str) -> List[Dict[str, Any]]:
        """List archived revisions of a stored definition, oldest first (#242)."""
        stem = self._resolve(filename).stem
        folder = self.storage_dir / "history"
        if not folder.is_dir():
            return []
        entries = []
        for file in folder.glob(f"{stem}.r*.*"):
            rev = file.name[len(stem) + 2:].split(".", 1)[0]
            if rev.isdigit():
                entries.append({"revision": int(rev), "file": str(file)})
        return sorted(entries, key=lambda e: e["revision"])

    def _resolve(self, filename: str) -> Path:
        """Return ``filename`` inside the store, refusing paths that would leave it."""
        name = Path(filename).name
        if not name or name != filename or name in (".", ".."):
            raise ValueError(f"Invalid Device UI definition file name '{filename}'")
        return self.storage_dir / name

    def load(self, name_or_path: Union[str, Path]) -> DeviceUISpec:
        """Load a DeviceUISpec from a file path or registered definition name (#242)."""
        p = Path(name_or_path)
        if not p.is_file():
            # Search in storage_dir
            for ext in (".yaml", ".yml", ".json"):
                candidate = self.storage_dir / f"{name_or_path}{ext}"
                if candidate.is_file():
                    p = candidate
                    break
                candidate_ui = self.storage_dir / f"{name_or_path}_ui{ext}"
                if candidate_ui.is_file():
                    p = candidate_ui
                    break

        if not p.is_file():
            raise FileNotFoundError(f"Device UI definition '{name_or_path}' not found in {self.storage_dir}")

        content = p.read_text(encoding="utf-8")
        return import_device_ui(content)

    def list_definitions(self) -> List[Dict[str, Any]]:
        """List all stored Device UI definitions (#242)."""
        if not self.storage_dir.exists():
            return []

        results: List[Dict[str, Any]] = []
        for file in self.storage_dir.glob("*"):
            if file.suffix.lower() in (".yaml", ".yml", ".json"):
                try:
                    spec = import_device_ui(file.read_text(encoding="utf-8"))
                    results.append({
                        "name": spec.identity.name,
                        "protocol_ref": spec.protocol_ref,
                        "version": spec.identity.version,
                        "schema_version": spec.schema_version,
                        "revision": spec.revision,
                        "file": str(file),
                        "filename": file.name,
                    })
                except Exception:
                    pass
        return results

    def delete(self, filename: str) -> bool:
        """Delete a stored definition file (#242)."""
        target = self._resolve(filename)
        if target.is_file():
            target.unlink()
            return True
        return False

    def find_for_protocol(self, protocol_name: str) -> Optional[DeviceUISpec]:
        """Find the matching DeviceUISpec for a given protocol name (#242)."""
        for item in self.list_definitions():
            if item.get("protocol_ref", "").lower() == protocol_name.lower():
                return self.load(item["file"])
        return None


def find_device_ui(spec: ProtocolSpec, file_stem: Optional[str] = None, store: Optional[DeviceUIStore] = None) -> Optional[DeviceUISpec]:
    """The saved Device UI definition for ``spec``: from the store first, then the bundled ``examples/device_ui``.

    A definition matches when its ``protocol_ref`` is the protocol's name or its file stem.
    """
    from omniuart.utils.resources import get_resource_path

    names = {spec.metadata.name.lower(), (file_stem or "").lower()} - {""}
    store = store or DeviceUIStore()
    for item in store.list_definitions():
        if str(item.get("protocol_ref", "")).lower() in names:
            return store.load(item["file"])
    bundled = get_resource_path("examples/device_ui")
    if bundled.is_dir():
        for file in sorted(bundled.iterdir()):
            if file.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue
            try:
                ui = import_device_ui(file.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 - a broken bundled file must not hide the inferred UI
                logger.warning("Skipping Device UI definition %s: %s", file.name, exc)
                continue
            if ui.protocol_ref.lower() in names:
                return ui
    return None


def load_device_ui(source: Union[str, Path, Dict[str, Any]]) -> DeviceUISpec:
    """Load and validate a DeviceUISpec from a file path, YAML/JSON string, or dict (#229, #242)."""
    if isinstance(source, dict):
        return migrate_ui_spec(source)

    if isinstance(source, Path) or (isinstance(source, str) and (source.endswith(".yaml") or source.endswith(".yml") or source.endswith(".json")) and Path(source).is_file()):
        content = Path(source).read_text(encoding="utf-8")
        return import_device_ui(content)

    if isinstance(source, str):
        return import_device_ui(source)

    raise ValueError("Invalid source type for DeviceUISpec")


def generate_device_ui_schema() -> Dict[str, Any]:
    """Generate JSON Schema dict for DeviceUISpec validation."""
    return DeviceUISpec.model_json_schema()


def infer_widget_for_field(
    field: FieldSpec,
    is_writable: bool = True,
    safety: Optional[CommandSafety] = None,
) -> WidgetSpec:
    """Infer intelligent control widget type and presentation parameters from field metadata (#231)."""
    val_type = field.type.value if hasattr(field.type, "value") else str(field.type)
    type_lower = val_type.lower()
    label = field.name.replace("_", " ").title()

    if not is_writable:
        if type_lower in ("bool", "boolean"):
            return WidgetSpec(widget_type="badge", field_ref=field.name, label=label)
        if type_lower in ("float32", "float64", "float", "double", "int8", "uint8", "int16", "uint16", "int32", "uint32"):
            return WidgetSpec(widget_type="gauge", field_ref=field.name, label=label, unit=field.unit, min=field.min, max=field.max)
        return WidgetSpec(widget_type="text", field_ref=field.name, label=label, unit=field.unit)

    if field.options or type_lower == "enum":
        return WidgetSpec(widget_type="dropdown", field_ref=field.name, label=label, options=field.options, unit=field.unit)

    if type_lower in ("bool", "boolean"):
        return WidgetSpec(widget_type="switch", field_ref=field.name, label=label)

    if field.min is not None and field.max is not None:
        if (field.max - field.min) <= 100 or type_lower.startswith("float"):
            step = 0.1 if type_lower.startswith("float") else 1.0
            return WidgetSpec(widget_type="slider", field_ref=field.name, label=label, min=field.min, max=field.max, step=step, unit=field.unit)
        return WidgetSpec(widget_type="number_input", field_ref=field.name, label=label, min=field.min, max=field.max, unit=field.unit)

    if type_lower in ("float32", "float64", "float", "double", "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64"):
        return WidgetSpec(widget_type="number_input", field_ref=field.name, label=label, unit=field.unit)

    return WidgetSpec(widget_type="text_input", field_ref=field.name, label=label)


def infer_device_ui_from_spec(spec: ProtocolSpec) -> DeviceUISpec:
    """Intelligently generate DeviceUISpec layout and control widgets from ProtocolSpec metadata (#231)."""
    identity = DeviceIdentity(
        name=spec.metadata.name,
        version=spec.metadata.version,
        description=spec.metadata.description,
        vendor=spec.metadata.author,
    )

    control_widgets: List[WidgetSpec] = []
    safety_rules: List[SafetyRuleSpec] = []

    for cmd in spec.commands:
        if cmd.safety in (CommandSafety.MUTATING, CommandSafety.DESTRUCTIVE):
            safety_rules.append(SafetyRuleSpec(command=cmd.name, require_confirmation=True, danger_zone=True))

        if cmd.parameters:
            for p in cmd.parameters:
                control_widgets.append(infer_widget_for_field(p, is_writable=True, safety=cmd.safety))
        else:
            control_widgets.append(WidgetSpec(widget_type="button", field_ref=cmd.name, label=f"Execute {cmd.name.title()}"))

    # Values the device reports: telemetry fields and the response fields of read-only commands
    telemetry_widgets: List[WidgetSpec] = []
    shown: set[str] = set()
    reported = [f for tel in spec.telemetry for f in tel.fields]
    reported += [f for cmd in spec.commands if cmd.is_read_only and cmd.response for f in cmd.response.fields]
    for f in reported:
        if f.name not in shown:
            shown.add(f.name)
            telemetry_widgets.append(infer_widget_for_field(f, is_writable=False))

    transfer_widgets: List[WidgetSpec] = []
    for cmd in spec.commands:
        cname = cmd.name.lower()
        if any(kw in cname for kw in ("firmware", "flash", "ota", "bootload", "transfer", "upload", "download", "dump", "log", "cert")):
            is_firmware = any(kw in cname for kw in ("firmware", "flash", "ota", "bootload"))
            transfer_widgets.append(
                WidgetSpec(
                    widget_type="firmware_update" if is_firmware else "file_transfer",
                    field_ref=cmd.name,
                    label=f"{cmd.name.replace('_', ' ').title()}",
                    transfer_type="firmware" if is_firmware else "binary",
                    supported_file_types=[".bin", ".hex", ".img", ".elf"] if is_firmware else [".bin", ".json", ".cfg", ".log", ".txt"],
                    max_size_bytes=16 * 1024 * 1024,
                    destructive=is_firmware or (cmd.safety is CommandSafety.MUTATING),
                    confirm_prompt=f"Are you sure you want to execute {cmd.name}? This modifies device state." if (is_firmware or cmd.safety is CommandSafety.MUTATING) else None,
                    safety_warning="Hazardous Operation: Do not interrupt or disconnect power/UART during transfer!" if is_firmware else None,
                )
            )

    groups: List[GroupSpec] = []
    if control_widgets:
        groups.append(GroupSpec(name="controls", title="Device Controls", layout="grid", widgets=control_widgets))
    if transfer_widgets:
        groups.append(GroupSpec(name="transfer", title="File & Blob Transfers", layout="grid", widgets=transfer_widgets))
    if telemetry_widgets:
        groups.append(GroupSpec(name="telemetry", title="Live Telemetry", layout="grid", widgets=telemetry_widgets))

    panels = [PanelSpec(name="main", title="Main Workspace", groups=groups)]

    return DeviceUISpec(
        identity=identity,
        protocol_ref=spec.metadata.name,
        panels=panels,
        safety_rules=safety_rules,
    )



class DeviceUIOverride(BaseModel):
    """Declarative UI customization and override definitions (#237)."""

    device_name: Optional[str] = None
    hidden_widgets: List[str] = Field(default_factory=list)
    widget_overrides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    panel_order: List[str] = Field(default_factory=list)

    def apply_overrides(self, ui_spec: DeviceUISpec) -> DeviceUISpec:
        """Apply customization overrides to an existing DeviceUISpec (#237)."""
        cloned = ui_spec.model_copy(deep=True)
        if self.device_name:
            cloned.identity.name = self.device_name

        for panel in cloned.panels:
            for group in panel.groups:
                filtered_widgets = []
                for w in group.widgets:
                    if w.field_ref and w.field_ref in self.hidden_widgets:
                        continue
                    if w.field_ref and w.field_ref in self.widget_overrides:
                        ov = self.widget_overrides[w.field_ref]
                        for k, v in ov.items():
                            if hasattr(w, k):
                                setattr(w, k, v)
                    filtered_widgets.append(w)
                group.widgets = filtered_widgets

        if self.panel_order:
            ordered = []
            panel_map = {p.name: p for p in cloned.panels}
            for pname in self.panel_order:
                if pname in panel_map:
                    ordered.append(panel_map[pname])
            for p in cloned.panels:
                if p not in ordered:
                    ordered.append(p)
            cloned.panels = ordered

        return cloned


def infer_device_model_from_traffic(
    frames: List[DecodedFrame],
    protocol_name: str = "Discovered Device",
) -> DeviceUISpec:
    """Infer proposed device model and UI layout from captured protocol traffic (#238)."""
    identity = DeviceIdentity(
        name=protocol_name,
        model="Traffic-Inferred Device",
        version="1.0.0-inferred",
        description=f"Auto-generated Device UI inferred from {len(frames)} captured frames",
    )

    observed_commands: Dict[str, Dict[str, Any]] = {}
    observed_telemetry: Dict[str, Dict[str, Any]] = {}

    for frame in frames:
        if not frame.ok:
            continue
        msg_name = frame.name or "unknown_command"
        if frame.kind == "command":
            if msg_name not in observed_commands:
                observed_commands[msg_name] = {"count": 0, "fields": {}}
            observed_commands[msg_name]["count"] += 1
            for fname, val in frame.fields.items():
                observed_commands[msg_name]["fields"][fname] = val
        else:
            for fname, val in frame.fields.items():
                if fname not in observed_telemetry:
                    observed_telemetry[fname] = {"sample": val, "type": type(val).__name__}

    control_widgets: List[WidgetSpec] = []
    for cmd_name, info in observed_commands.items():
        if info["fields"]:
            for fname, val in info["fields"].items():
                w_type = "slider" if isinstance(val, (int, float)) and not isinstance(val, bool) else "text_input"
                control_widgets.append(WidgetSpec(
                    widget_type=w_type,
                    field_ref=f"{cmd_name}.{fname}",
                    label=f"{cmd_name} {fname}".replace("_", " ").title(),
                ))
        else:
            control_widgets.append(WidgetSpec(
                widget_type="button",
                field_ref=cmd_name,
                label=f"Execute {cmd_name.replace('_', ' ').title()}",
            ))

    telemetry_widgets: List[WidgetSpec] = []
    for tel_name, info in observed_telemetry.items():
        val = info["sample"]
        w_type = "gauge" if isinstance(val, (int, float)) and not isinstance(val, bool) else "badge"
        telemetry_widgets.append(WidgetSpec(
            widget_type=w_type,
            field_ref=tel_name,
            label=tel_name.replace("_", " ").title(),
        ))

    groups = []
    if control_widgets:
        groups.append(GroupSpec(name="controls", title="Inferred Controls", layout="grid", widgets=control_widgets))
    if telemetry_widgets:
        groups.append(GroupSpec(name="telemetry", title="Inferred Telemetry", layout="grid", widgets=telemetry_widgets))

    return DeviceUISpec(
        identity=identity,
        protocol_ref=protocol_name,
        panels=[PanelSpec(name="inferred", title="Inferred Device Console", groups=groups)],
    )
