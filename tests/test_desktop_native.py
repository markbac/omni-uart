"""Unit tests for Native Tkinter Desktop Application views and controls."""

from __future__ import annotations

import os
import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.desktop.app import OmniUARTDesktopApp
from omniuart.desktop.views import build_frame_payload


def test_build_frame_payload(tmp_path):
    """Test frame payload generation for binary and delimited protocol commands."""
    catalog = CatalogManager()
    summary = catalog.catalog_summary()
    assert summary["protocols_found"] > 0

    p_filename = summary["protocols"][0]["filename"]
    spec = catalog.get_protocol(p_filename)
    assert spec is not None
    assert len(spec.commands) > 0

    cmd = spec.commands[0]
    payload = build_frame_payload(spec, cmd, {})
    assert isinstance(payload, bytes)
    assert len(payload) > 0


@pytest.mark.skipif(os.environ.get("HEADLESS") == "1", reason="Headless environment without display server")
def test_desktop_app_initialization():
    """Test OmniUARTDesktopApp widget initialization and tab creation."""
    try:
        app = OmniUARTDesktopApp()
        app.update()
        
        # Verify connection toolbar exists
        assert hasattr(app, "toolbar")
        assert app.toolbar.is_connected is False
        
        # Verify notebook tabs count is 5
        assert app.notebook.index("end") == 5

        # Toggle connection state
        app.toolbar._toggle_connection()
        assert app.toolbar.is_connected is True

        # Test CommsStreamerView dual decoded formatting and recording toggle
        comms_tab = app.comms_view
        comms_tab._toggle_recording()
        assert comms_tab.is_recording is True
        comms_tab.log("TX", b"AT+CSQ\r\n", "AT Command")
        comms_tab.log("RX", b"\xAA\x01\x10\x20\xFF", "Binary Packet")
        comms_tab._send_macro("⚡ AT Ping", b"AT\r\n")
        comms_tab._toggle_recording()
        assert comms_tab.is_recording is False

        console_text = comms_tab.console.get("1.0", "end-1c")
        assert "Decoded:" in console_text
        assert "Length:" in console_text
        assert "SESSION RECORDING" in console_text

        # Test Global Active Protocol selection & auto serial port config
        assert app.toolbar.proto_var.get() == "None"
        protocols = app.catalog.catalog_summary().get("protocols", [])
        if protocols:
            p_name = protocols[0]["name"]
            app.toolbar.proto_var.set(p_name)
            app.toolbar._on_proto_select()
            assert app.dashboard_view.proto_var.get() == p_name
            assert app.catalog_view.proto_filter_var.get() == p_name

        # Test TelemetryPlotterView polling toggle & multi-channel parsing
        plotter = app.plotter_view
        plotter._toggle_auto_poll()
        assert plotter.is_polling is True
        plotter.push_telemetry_bytes(b"+CSQ: 24, 9\r\n")
        assert len(plotter.channel_1_points) > 0
        assert len(plotter.channel_2_points) > 0
        plotter._toggle_auto_poll()
        assert plotter.is_polling is False

        app.destroy()
    except Exception as e:
        # If running in no-display environment, handle gracefully
        if "no display name" in str(e).lower() or "tclerror" in str(e).lower():
            pytest.skip(f"No display environment: {e}")
        else:
            raise e
