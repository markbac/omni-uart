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
