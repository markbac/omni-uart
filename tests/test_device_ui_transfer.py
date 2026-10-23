"""Unit tests for transfer-aware Device UI controls (#246, #243)."""

from __future__ import annotations

from omniuart.core.device_ui import (
    DeviceIdentity,
    DeviceUISpec,
    GroupSpec,
    PanelSpec,
    WidgetSpec,
    infer_device_ui_from_spec,
)
from omniuart.core.models import (
    CommandSafety,
    CommandSpec,
    FramingConfig,
    FramingType,
    ProtocolMeta,
    ProtocolSpec,
    SerialConfig,
)
from omniuart.dashboard_generator import generate_device_dashboard_html


def test_widget_spec_transfer_attributes() -> None:
    """Verify WidgetSpec supports file transfer metadata and safety fields."""
    widget = WidgetSpec(
        widget_type="firmware_update",
        field_ref="flash_firmware",
        label="Firmware Update",
        transfer_type="firmware",
        supported_file_types=[".bin", ".hex"],
        max_size_bytes=4 * 1024 * 1024,
        destructive=True,
        confirm_prompt="Flash MCU firmware?",
        safety_warning="Do not unplug power during flash!",
    )

    assert widget.widget_type == "firmware_update"
    assert widget.destructive is True
    assert widget.supported_file_types == [".bin", ".hex"]
    assert widget.max_size_bytes == 4 * 1024 * 1024
    assert "Flash MCU" in str(widget.confirm_prompt)


def test_infer_device_ui_creates_transfer_group() -> None:
    """Verify infer_device_ui_from_spec automatically creates transfer controls for firmware/flash commands."""
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="FlashableNode", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.DELIMITED),
        commands=[
            CommandSpec(name="ping", id=1, safety=CommandSafety.READ_ONLY),
            CommandSpec(name="flash_firmware", id=2, safety=CommandSafety.MUTATING),
        ],
    )

    ui_spec = infer_device_ui_from_spec(spec)
    assert ui_spec.identity.name == "FlashableNode"

    # Verify transfer group exists
    main_panel = ui_spec.panels[0]
    group_names = [g.name for g in main_panel.groups]
    assert "transfer" in group_names

    transfer_group = next(g for g in main_panel.groups if g.name == "transfer")
    assert len(transfer_group.widgets) >= 1
    w = transfer_group.widgets[0]
    assert w.widget_type == "firmware_update"
    assert w.destructive is True
    assert ".bin" in (w.supported_file_types or [])


def test_dashboard_renders_transfer_controls_and_safety_alerts() -> None:
    """Verify dashboard HTML includes file selector, progress bar, action buttons, and safety alerts."""
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="BootloaderDevice", version="2.1.0", author="Acme Corp"),
        serial_config=SerialConfig(baudrate=921600),
        framing=FramingConfig(type=FramingType.DELIMITED),
        commands=[
            CommandSpec(name="program_flash", id=10, safety=CommandSafety.MUTATING),
        ],
    )

    widget = WidgetSpec(
        widget_type="firmware_update",
        field_ref="program_flash",
        label="Flash Main Firmware",
        transfer_type="firmware",
        supported_file_types=[".bin", ".img"],
        max_size_bytes=8 * 1024 * 1024,
        destructive=True,
        confirm_prompt="Proceed with bootloader flashing?",
        safety_warning="Hazard: Power loss will brick the board!",
    )

    ui_spec = DeviceUISpec(
        identity=DeviceIdentity(name="BootloaderDevice", model="BL-500", vendor="Acme"),
        protocol_ref="BootloaderDevice",
        panels=[
            PanelSpec(
                name="main",
                title="Device Console",
                groups=[
                    GroupSpec(
                        name="firmware",
                        title="Firmware Operations",
                        layout="grid",
                        widgets=[widget],
                    )
                ],
            )
        ],
    )

    html = generate_device_dashboard_html(spec, ui_spec=ui_spec)

    assert "<!DOCTYPE html>" in html
    assert "BootloaderDevice" in html
    assert "transfer-card" in html
    assert 'data-transfer-ref="program_flash"' in html
    assert 'data-destructive="true"' in html
    assert 'accept=".bin,.img"' in html
    assert "progress-bar-fill" in html
    assert "Start Transfer" in html
    assert "Cancel" in html
    assert "Retry" in html
    assert "Power loss will brick the board!" in html
    assert "ETA: --" in html
    assert "IDLE" in html


def test_dashboard_escapes_transfer_metadata_against_xss() -> None:
    """Verify user/device provided transfer metadata is strictly escaped to prevent injection (#316, #246)."""
    spec = ProtocolSpec(
        metadata=ProtocolMeta(name="SafeNode", version="1.0.0"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.DELIMITED),
        commands=[CommandSpec(name="cmd", id=1)],
    )

    xss_injection = '<script>alert("xss")</script>'
    widget = WidgetSpec(
        widget_type="file_transfer",
        field_ref="upload_xss",
        label=f"Upload {xss_injection}",
        transfer_type=xss_injection,
        supported_file_types=[".txt", xss_injection],
        confirm_prompt=xss_injection,
        safety_warning=xss_injection,
        destructive=True,
    )

    ui_spec = DeviceUISpec(
        identity=DeviceIdentity(name="SafeNode"),
        protocol_ref="SafeNode",
        panels=[
            PanelSpec(
                name="p",
                title="P",
                groups=[GroupSpec(name="g", title="G", widgets=[widget])],
            )
        ],
    )

    html = generate_device_dashboard_html(spec, ui_spec=ui_spec)

    assert "<script>alert" not in html
    assert "&lt;script&gt;alert" in html
