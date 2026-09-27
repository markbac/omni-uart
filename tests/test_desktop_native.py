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

        # Test CommsStreamerView dual decoded formatting
        comms_tab = app.comms_view
        comms_tab.log("TX", b"AT+CSQ\r\n", "AT Command")
        comms_tab.log("RX", b"\xAA\x01\x10\x20\xFF", "Binary Packet")
        console_text = comms_tab.console.get("1.0", "end-1c")
        assert "Decoded:" in console_text
        assert "Length:" in console_text

        app.destroy()
    except Exception as e:
        # If running in no-display environment, handle gracefully
        if "no display name" in str(e).lower() or "tclerror" in str(e).lower():
            pytest.skip(f"No display environment: {e}")
        else:
            raise e
