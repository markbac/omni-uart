"""Tests for Device UI Designer and Versioning/Persistence (#241, #242)."""

from __future__ import annotations

from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from omniuart.core.device_ui import (
    DeviceIdentity,
    DeviceUISpec,
    DeviceUIStore,
    GroupSpec,
    PanelSpec,
    SafetyRuleSpec,
    WidgetSpec,
    check_protocol_compatibility,
    export_device_ui,
    import_device_ui,
    infer_device_ui_from_spec,
    migrate_ui_spec,
)
from omniuart.core.models import (
    CommandSafety,
    CommandSpec,
    FieldSpec,
    FieldType,
    FramingConfig,
    FramingType,
    ProtocolMeta,
    ProtocolSpec,
    SerialConfig,
    TelemetrySpec,
)
from omniuart.designer import DeviceUIDesigner, generate_designer_html
from omniuart.ui.app import app


@pytest.fixture
def sample_protocol() -> ProtocolSpec:
    """Fixture returning a standard ProtocolSpec for testing."""
    return ProtocolSpec(
        metadata=ProtocolMeta(name="SensorMaster", version="2.1.0", author="Test Team"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY),
        commands=[
            CommandSpec(
                name="ping",
                id=1,
                safety=CommandSafety.READ_ONLY,
            ),
            CommandSpec(
                name="set_threshold",
                id=2,
                safety=CommandSafety.MUTATING,
                parameters=[
                    FieldSpec(name="sensor_id", type=FieldType.UINT8),
                    FieldSpec(name="threshold_val", type=FieldType.FLOAT32, unit="°C", min=0.0, max=100.0),
                ],
            ),
            CommandSpec(
                name="reboot",
                id=3,
                safety=CommandSafety.DESTRUCTIVE,
            ),
        ],
        telemetry=[
            TelemetrySpec(
                name="env_status",
                id=10,
                fields=[
                    FieldSpec(name="temperature", type=FieldType.FLOAT32, unit="°C"),
                    FieldSpec(name="humidity", type=FieldType.FLOAT32, unit="%"),
                ],
            )
        ],
    )


# -----------------------------------------------------------------------------
# #242: Versioning, Compatibility & Migration
# -----------------------------------------------------------------------------
def test_device_ui_compatibility_checker_success(sample_protocol: ProtocolSpec) -> None:
    """Verify that a matching DeviceUISpec passes compatibility checks without errors (#242)."""
    designer = DeviceUIDesigner(sample_protocol)
    report = designer.validate()

    assert report.is_compatible is True
    assert len(report.errors) == 0
    assert len(report.missing_commands) == 0
    assert len(report.missing_fields) == 0


def test_device_ui_compatibility_checker_catches_missing_elements(sample_protocol: ProtocolSpec) -> None:
    """Verify that missing commands, fields, or mismatched versions are reported (#242)."""
    ui_spec = DeviceUISpec(
        schema_version="1.0.0",
        compatible_protocol_version="1.0.0",  # differs from 2.1.0
        identity=DeviceIdentity(name="SensorMaster"),
        protocol_ref="SensorMaster",
        safety_rules=[
            SafetyRuleSpec(command="non_existent_command", require_confirmation=True),
        ],
        panels=[
            PanelSpec(
                name="main",
                title="Main",
                groups=[
                    GroupSpec(
                        name="controls",
                        title="Controls",
                        widgets=[
                            WidgetSpec(widget_type="button", field_ref="unknown_action", label="Do Unknown"),
                            WidgetSpec(widget_type="slider", field_ref="set_threshold.non_existent_param", label="Bad Param"),
                            WidgetSpec(widget_type="gauge", field_ref="ghost_field", label="Ghost Field"),
                        ],
                    )
                ],
            )
        ],
    )

    report = check_protocol_compatibility(ui_spec, sample_protocol)
    assert report.is_compatible is False
    assert report.protocol_version_matches is False
    assert "non_existent_command" in report.missing_commands
    assert "unknown_action" in report.missing_commands
    assert "set_threshold.non_existent_param" in report.missing_fields
    assert "ghost_field" in report.missing_fields
    assert len(report.warnings) > 0


def test_device_ui_migration_from_legacy_data() -> None:
    """Verify that older unversioned or controls-based definitions migrate cleanly (#242)."""
    legacy_data = {
        "identity": "Legacy Smart Sensor",
        "protocol": "sensor_v1",
        "controls": [
            {"widget_type": "slider", "field_ref": "target_speed", "label": "Target Speed"},
            {"widget_type": "switch", "field_ref": "enable_output", "label": "Output Power"},
        ],
    }

    migrated = migrate_ui_spec(legacy_data, target_version="1.0.0")
    assert migrated.schema_version == "1.0.0"
    assert migrated.identity.name == "Legacy Smart Sensor"
    assert migrated.protocol_ref == "sensor_v1"
    assert len(migrated.panels) == 1
    assert len(migrated.panels[0].groups) == 1
    assert len(migrated.panels[0].groups[0].widgets) == 2


def test_device_ui_export_and_import_roundtrip(sample_protocol: ProtocolSpec) -> None:
    """Verify lossless export and import roundtrip in YAML and JSON (#242)."""
    designer = DeviceUIDesigner(sample_protocol)
    original_spec = designer.ui_spec

    # Test YAML roundtrip
    yaml_text = export_device_ui(original_spec, format="yaml")
    assert "protocol_ref: SensorMaster" in yaml_text
    imported_yaml = import_device_ui(yaml_text)
    assert imported_yaml.protocol_ref == original_spec.protocol_ref
    assert len(imported_yaml.panels) == len(original_spec.panels)

    # Test JSON roundtrip
    json_text = export_device_ui(original_spec, format="json")
    assert '"protocol_ref": "SensorMaster"' in json_text
    imported_json = import_device_ui(json_text)
    assert imported_json.protocol_ref == original_spec.protocol_ref


def test_device_ui_store_lifecycle(tmp_path: Path, sample_protocol: ProtocolSpec) -> None:
    """Verify DeviceUIStore save, load, list, search, and delete functionality (#242)."""
    store = DeviceUIStore(storage_dir=tmp_path)
    designer = DeviceUIDesigner(sample_protocol, store=store)

    # Save
    saved_path = designer.save(filename="sensor_master.yaml")
    assert saved_path.is_file()

    # List
    definitions = store.list_definitions()
    assert len(definitions) == 1
    assert definitions[0]["protocol_ref"] == "SensorMaster"

    # Load by path and by stem
    loaded1 = store.load(saved_path)
    assert loaded1.protocol_ref == "SensorMaster"
    loaded2 = store.load("sensor_master")
    assert loaded2.protocol_ref == "SensorMaster"

    # Search for protocol
    found = store.find_for_protocol("SensorMaster")
    assert found is not None
    assert found.identity.name == "SensorMaster"

    # Delete
    deleted = store.delete("sensor_master.yaml")
    assert deleted is True
    assert len(store.list_definitions()) == 0


# -----------------------------------------------------------------------------
# #241: Visual Device UI Designer
# -----------------------------------------------------------------------------
def test_device_ui_designer_arrangement(sample_protocol: ProtocolSpec) -> None:
    """Verify adding, removing, and reordering panels, groups, and widgets (#241)."""
    designer = DeviceUIDesigner(sample_protocol)

    # Add panel
    panel = designer.add_panel("diagnostics", "Diagnostics Center")
    assert panel.name == "diagnostics"
    assert len(designer.ui_spec.panels) == 2

    # Add group
    group = designer.add_group("diagnostics", "meters", "Power Meters")
    assert group.name == "meters"

    # Add widget
    widget = WidgetSpec(widget_type="gauge", field_ref="voltage", label="Bus Voltage", unit="V")
    designer.add_widget("diagnostics", "meters", widget)
    assert len(group.widgets) == 1

    # Update widget
    updated = designer.update_widget("voltage", unit="mV", max=5000.0)
    assert updated is True
    assert group.widgets[0].unit == "mV"
    assert group.widgets[0].max == 5000.0

    # Reorder panels
    designer.reorder_panels(["diagnostics", "main"])
    assert designer.ui_spec.panels[0].name == "diagnostics"

    # Remove widget
    removed_widget = designer.remove_widget("diagnostics", "meters", "voltage")
    assert removed_widget is True
    assert len(group.widgets) == 0

    # Remove panel
    removed_panel = designer.remove_panel("diagnostics")
    assert removed_panel is True
    assert len(designer.ui_spec.panels) == 1


def test_device_ui_designer_field_binding(sample_protocol: ProtocolSpec) -> None:
    """Verify binding protocol parameters and telemetry fields into control widgets (#241)."""
    designer = DeviceUIDesigner(sample_protocol)

    # Bind command parameter
    w_thresh = designer.bind_field("threshold_val")
    assert w_thresh.field_ref == "threshold_val"
    assert w_thresh.widget_type == "slider"
    assert w_thresh.unit == "°C"

    # Bind telemetry field
    w_temp = designer.bind_field("temperature")
    assert w_temp.field_ref == "temperature"
    assert w_temp.widget_type == "gauge"

    # Bind command as button
    w_reboot = designer.bind_field("reboot")
    assert w_reboot.field_ref == "reboot"
    assert w_reboot.widget_type == "button"

    # Safety rules
    designer.add_safety_rule("reboot", require_confirmation=True, danger_zone=True, warning_message="Device will restart")
    assert any(r.command == "reboot" and r.danger_zone for r in designer.ui_spec.safety_rules)

    designer.remove_safety_rule("reboot")
    assert not any(r.command == "reboot" for r in designer.ui_spec.safety_rules)


def test_device_ui_designer_html_rendering_and_escaping(sample_protocol: ProtocolSpec) -> None:
    """Verify HTML generation, injection prevention, and template layout (#241, #316)."""
    html_output = generate_designer_html(sample_protocol)

    # Verification of key structural elements
    assert "<title>Device UI Designer - SensorMaster</title>" in html_output
    assert "SensorMaster v2.1.0" in html_output
    assert 'id="protocol-commands"' in html_output
    assert 'id="canvas-area"' in html_output
    assert 'id="property-inspector"' in html_output
    assert 'id="btn-validate"' in html_output
    assert 'id="btn-preview"' in html_output
    assert 'id="btn-export-yaml"' in html_output
    assert 'id="btn-save"' in html_output

    # Injection safety check (#316)
    injection_protocol = ProtocolSpec(
        metadata=ProtocolMeta(name='<script>alert("xss")</script>', version="1.0.0"),
        serial_config=SerialConfig(baudrate=9600),
        framing=FramingConfig(type=FramingType.BINARY),
        commands=[
            CommandSpec(name='<b>danger_cmd</b>', id=1, safety=CommandSafety.MUTATING)
        ],
    )
    safe_html = generate_designer_html(injection_protocol)
    assert '<script>alert("xss")</script>' not in safe_html
    assert '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;' in safe_html
    assert '&lt;b&gt;danger_cmd&lt;/b&gt;' in safe_html


def test_device_ui_win32_classic_theme_generation(sample_protocol: ProtocolSpec) -> None:
    """Verify that setting theme='win32' renders classic desktop layout with tabs and LCD (#241, #242)."""
    from omniuart.dashboard_generator import generate_device_dashboard_html

    ui_spec = DeviceUISpec(
        theme="win32",
        identity=DeviceIdentity(name="G460 Product Config Tool", version="1.42"),
        protocol_ref="SensorMaster",
        panels=[
            PanelSpec(
                name="info",
                title="Info",
                groups=[
                    GroupSpec(
                        name="lcd",
                        title="Display",
                        widgets=[
                            WidgetSpec(widget_type="lcd_matrix", label="LCD Display", field_ref="read_lcd")
                        ],
                    )
                ],
            ),
            PanelSpec(
                name="config",
                title="Config",
                groups=[
                    GroupSpec(
                        name="voss",
                        title="VOSS",
                        widgets=[
                            WidgetSpec(widget_type="paired_register", label="Flow threshold", field_ref="threshold_val", unit="lph")
                        ],
                    )
                ],
            ),
        ],
    )

    html_res = generate_device_dashboard_html(sample_protocol, ui_spec)
    assert "G460 Product Config Tool - V1.42" in html_res
    assert "win32-tab-button" in html_res
    assert "win32-tab-pane" in html_res
    assert "LCD Display" in html_res
    assert "win32-lcd-grid" in html_res
    assert "Flow threshold" in html_res
    assert "win32-btn-get" in html_res
    assert "win32-btn-set" in html_res
    assert "Clear Text" in html_res
    assert "Log Payloads" in html_res
    assert "win32-log-textarea" in html_res


# -----------------------------------------------------------------------------
# Web API endpoints for Designer (#241, #242)
# -----------------------------------------------------------------------------
def test_designer_web_api_endpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify FastAPI routes for Designer and persistence (#241, #242)."""
    monkeypatch.chdir(tmp_path)  # the store writes to .omniuart/ui under the working directory
    client = TestClient(app)

    # GET /designer
    res = client.get("/designer")
    assert res.status_code == 200
    assert "OmniUART UI Designer" in res.text

    # GET /api/designer/definitions
    res_defs = client.get("/api/designer/definitions")
    assert res_defs.status_code == 200
    assert "definitions" in res_defs.json()

    # POST /api/designer/validate with valid payload
    val_payload = {
        "protocol": "ascii_device",
        "ui_spec": {
            "identity": {"name": "AsciiDevice"},
            "protocol_ref": "AsciiDevice",
            "panels": [
                {
                    "name": "main",
                    "title": "Main",
                    "groups": [
                        {
                            "name": "controls",
                            "title": "Controls",
                            "widgets": [
                                {"widget_type": "button", "field_ref": "TEST", "label": "Test Device"}
                            ]
                        }
                    ]
                }
            ]
        }
    }
    res_val = client.post("/api/designer/validate", json=val_payload)
    assert res_val.status_code == 200
    assert res_val.json()["is_compatible"] is True

    # POST /api/designer/save
    save_payload = {
        "ui_spec": val_payload["ui_spec"],
        "format": "yaml",
    }
    res_save = client.post("/api/designer/save", json=save_payload)
    assert res_save.status_code == 200
    assert res_save.json()["ok"] is True


def test_designer_initial_data_is_parseable_json(sample_protocol: ProtocolSpec) -> None:
    """The embedded state must be plain JSON: browsers do not decode entities inside <script> (#241)."""
    import json
    import re

    hostile = sample_protocol.model_copy(deep=True)
    hostile.metadata.description = '</script><script>alert(1)</script> & "quotes"'
    page = generate_designer_html(hostile)
    match = re.search(r'<script type="application/json" id="initial-data">(.*?)</script>', page, re.S)
    assert match is not None
    data = json.loads(match.group(1))
    assert data["protocol"]["metadata"]["description"] == hostile.metadata.description
    assert "</script><script>" not in match.group(1)


def test_device_ui_store_rejects_paths_outside_the_store(tmp_path: Path, sample_protocol: ProtocolSpec) -> None:
    """A protocol_ref or file name must not write or delete outside the store (#242)."""
    store = DeviceUIStore(storage_dir=tmp_path / "ui")
    spec = infer_device_ui_from_spec(sample_protocol)
    spec.protocol_ref = "../../escape"
    path = store.save(spec)
    assert path.parent == tmp_path / "ui"
    assert path.name == "escape_ui.yaml"
    with pytest.raises(ValueError):
        store.save(spec, filename="../outside.yaml")
    with pytest.raises(ValueError):
        store.delete("../ui/escape_ui.yaml")


def test_device_ui_store_versions_changed_definitions(tmp_path: Path, sample_protocol: ProtocolSpec) -> None:
    """Saving changed content bumps the revision and archives the previous file (#242)."""
    store = DeviceUIStore(storage_dir=tmp_path)
    spec = infer_device_ui_from_spec(sample_protocol)
    path = store.save(spec)
    assert store.load(path).revision == 1
    assert store.save(spec) == path and store.history(path.name) == []  # unchanged: no new revision

    spec.identity.name = "Renamed"
    store.save(spec)
    assert store.load(path).revision == 2
    history = store.history(path.name)
    assert [h["revision"] for h in history] == [1]
    assert store.load(history[0]["file"]).identity.name == "SensorMaster"


def test_designer_export_preview_and_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Export, preview and error paths of the designer API (#241)."""
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    ui = {"identity": {"name": "AsciiDevice"}, "protocol_ref": "AsciiDevice", "panels": []}

    res = client.post("/api/designer/export", json={"ui_spec": ui, "format": "yaml"})
    assert res.status_code == 200
    assert "protocol_ref: AsciiDevice" in res.text

    res = client.post("/api/designer/preview", json={"protocol": "ascii_device", "ui_spec": ui})
    assert res.status_code == 200
    assert "<html" in res.text.lower()

    assert client.post("/api/designer/save", json={"ui_spec": {"panels": "bad"}}).status_code == 422
    assert client.get("/designer/no_such_protocol_xyz").status_code == 404
