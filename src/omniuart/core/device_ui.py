"""Declarative Device UI Schema Subsystem for OmniUART (#229).

Defines a declarative Device UI Schema separate from protocol framing, describing device identity,
capabilities, controls, telemetry, navigation, safety rules, grouping, and widget presentation hints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
import yaml

from omniuart.core.models import CommandSafety, FieldSpec, ProtocolSpec


class DeviceIdentity(BaseModel):
    """Device identity metadata."""

    name: str
    model: str = "Generic Device"
    vendor: Optional[str] = None
    version: str = "1.0.0"
    description: Optional[str] = None
    icon: Optional[str] = "device"


class WidgetSpec(BaseModel):
    """Declarative UI control or telemetry widget element."""

    widget_type: str = Field(description="Widget type: slider, switch, button, dropdown, gauge, line_plot, badge, text")
    field_ref: Optional[str] = Field(default=None, description="Mapped protocol field or command parameter")
    label: str
    icon: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    unit: Optional[str] = None
    options: Optional[Dict[Any, str]] = None
    presentation_hints: Dict[str, Any] = Field(default_factory=dict)


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


class DeviceUISpec(BaseModel):
    """Declarative Device UI Specification model."""

    schema_version: str = "1.0.0"
    identity: DeviceIdentity
    protocol_ref: str
    panels: List[PanelSpec] = Field(default_factory=list)
    safety_rules: List[SafetyRuleSpec] = Field(default_factory=list)


def load_device_ui(source: Union[str, Path, Dict[str, Any]]) -> DeviceUISpec:
    """Load and validate a DeviceUISpec from a file path, YAML/JSON string, or dict."""
    if isinstance(source, dict):
        return DeviceUISpec.model_validate(source)

    if isinstance(source, Path) or (isinstance(source, str) and (source.endswith(".yaml") or source.endswith(".yml") or source.endswith(".json")) and Path(source).is_file()):
        content = Path(source).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return DeviceUISpec.model_validate(data)

    if isinstance(source, str):
        data = yaml.safe_load(source)
        return DeviceUISpec.model_validate(data)

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
        if cmd.safety is CommandSafety.MUTATING:
            safety_rules.append(SafetyRuleSpec(command=cmd.name, require_confirmation=True, danger_zone=True))

        if cmd.parameters:
            for p in cmd.parameters:
                control_widgets.append(infer_widget_for_field(p, is_writable=True, safety=cmd.safety))
        else:
            control_widgets.append(WidgetSpec(widget_type="button", field_ref=cmd.name, label=f"Execute {cmd.name.title()}"))

    telemetry_widgets: List[WidgetSpec] = []
    for tel in spec.telemetry:
        for f in tel.fields:
            telemetry_widgets.append(infer_widget_for_field(f, is_writable=False))

    groups: List[GroupSpec] = []
    if control_widgets:
        groups.append(GroupSpec(name="controls", title="Device Controls", layout="grid", widgets=control_widgets))
    if telemetry_widgets:
        groups.append(GroupSpec(name="telemetry", title="Live Telemetry", layout="grid", widgets=telemetry_widgets))

    panels = [PanelSpec(name="main", title="Main Workspace", groups=groups)]

    return DeviceUISpec(
        identity=identity,
        protocol_ref=spec.metadata.name,
        panels=panels,
        safety_rules=safety_rules,
    )
