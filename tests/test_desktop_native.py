"""Unit tests for Native Tkinter Desktop Application views and controls."""

from __future__ import annotations

import os
import time
import tkinter as tk

import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.core.models import CommandSafety, ProtocolSpec
from omniuart.core.transport import list_available_ports
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


def _wait(app, condition, timeout: float = 10.0) -> None:
    """Pump the Tk event loop (which also drains the device-thread queue) until ``condition()`` holds."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.update()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("condition not reached in time")


@pytest.fixture()
def app():
    if os.environ.get("HEADLESS") == "1":
        pytest.skip("Headless environment without display server")
    try:
        instance = OmniUARTDesktopApp()
        instance.update()
    except tk.TclError as exc:
        pytest.skip(f"No display environment: {exc}")
    yield instance
    instance.destroy()


def _select_protocol(app, filename: str) -> ProtocolSpec:
    spec = app.catalog.get_protocol(filename)
    assert spec is not None
    app.toolbar.proto_var.set(spec.metadata.name)
    app.toolbar._on_proto_select()
    return spec


def _connect_virtual(app) -> None:
    app.toolbar.port_var.set("virtual")
    app.toolbar._toggle_connection()
    _wait(app, lambda: app.toolbar.is_connected)


def test_desktop_app_initialization(app) -> None:
    assert app.notebook.index("end") == 5
    assert app.toolbar.is_connected is False
    # Only real ports and the explicit virtual device are offered; no invented COM/tty list.
    offered = list(app.toolbar.port_combo["values"])
    assert "virtual" in offered
    assert "COM1" not in offered or "COM1" in [p["device"] for p in list_available_ports()]

    comms = app.comms_view
    comms._toggle_recording()
    comms.log("TX", b"AT+CSQ\r\n", "AT Command")
    comms.log("RX", b"\xAA\x01\x10\x20\xFF", "Binary Packet")
    comms._toggle_recording()
    text = comms.console.get("1.0", "end-1c")
    assert "Decoded:" in text and "Length:" in text and "SESSION RECORDING" in text

    protocols = app.catalog.catalog_summary().get("protocols", [])
    assert protocols
    app.toolbar.proto_var.set(protocols[0]["name"])
    app.toolbar._on_proto_select()
    assert app.dashboard_view.proto_var.get() == protocols[0]["name"]
    assert app.catalog_view.proto_filter_var.get() == protocols[0]["name"]


def test_connect_failure_leaves_gui_disconnected(app) -> None:
    app.toolbar.port_var.set("/dev/omniuart-no-such-port")
    app.toolbar._toggle_connection()
    _wait(app, lambda: str(app.toolbar.connect_btn["state"]) == "normal")
    assert app.toolbar.is_connected is False
    assert app.device.connected is False
    assert "Could not open" in app.status_text_var.get()


def test_send_without_a_link_transmits_nothing(app) -> None:
    spec = _select_protocol(app, "binary_sensor_node")
    assert app._handle_send(spec, "get_readings", {"channel": 1}) is None
    assert "Not connected" in app.status_text_var.get()
    assert app.tx_bytes_count == 0
    assert app.plotter_view.channel_1_points == []


def test_virtual_link_send_logs_tx_and_decoded_rx_and_plots_only_rx(app) -> None:
    spec = _select_protocol(app, "binary_sensor_node")
    _connect_virtual(app)
    assert app.device.simulated and "simulation" in app.status_text_var.get()

    future = app._handle_send(spec, "get_readings", {"channel": 1})
    assert future is not None
    _wait(app, lambda: "answered in" in app.status_text_var.get())

    console = app.comms_view.console.get("1.0", "end-1c")
    assert "[TX]" in console and "[RX]" in console and "channel=1" in console
    exchange = future.result()
    numeric = [v for v in exchange.fields.values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert numeric, "protocol response should have a numeric field"
    assert app.plotter_view.channel_1_points == [float(numeric[0])]
    assert app.rx_bytes_count == len(exchange.response_bytes) > 0

    app.toolbar._toggle_connection()
    _wait(app, lambda: not app.toolbar.is_connected)
    assert app.device.connected is False


def test_poll_targets_are_only_safe_commands(app) -> None:
    targets = app.plotter_view.poll_targets
    assert targets
    for spec, name in targets.values():
        cmd = spec.get_command(name)
        assert "dashboard" in cmd.tags and cmd.response is not None
        assert all(p.default is not None for p in cmd.parameters)
    assert not any("AT Ping" in label or "Modbus" in label for label in targets)


def test_plotter_ignores_non_numeric_and_plots_decoded_numbers(app) -> None:
    plot = app.plotter_view
    plot.push_fields({"text": "+CSQ: 24,9"})
    assert plot.channel_1_points == []
    plot.push_fields({"temp": 21.5, "ok": True, "humidity": 40})
    assert plot.channel_1_points == [21.5] and plot.channel_2_points == [40.0]


def test_script_runner_view_reports_real_results(app) -> None:
    view = app.script_view
    # Not connected: refuses to run and does not claim success.
    view._run_script()
    assert "Not connected" in view.log_text.get("1.0", "end-1c")
    assert "completed successfully" not in view.log_text.get("1.0", "end-1c")

    _connect_virtual(app)
    view._run_script()
    _wait(app, lambda: "Script PASSED" in view.log_text.get("1.0", "end-1c") or "Script FAILED" in view.log_text.get("1.0", "end-1c") or "Script aborted" in view.log_text.get("1.0", "end-1c"))
    results = [view.steps_tree.set(item, "result") for item in view.steps_tree.get_children()]
    assert results and all(r in {"PASSED", "FAILED", "ERROR", "SKIPPED"} for r in results)
    assert str(view.run_btn["state"]) == "normal"


def test_mutating_command_needs_confirmation_and_declining_sends_nothing(app, monkeypatch) -> None:
    from tkinter import messagebox

    spec = _select_protocol(app, "binary_sensor_node")
    _connect_virtual(app)
    cmd = spec.get_command("set_sampling_rate").model_copy(update={"safety": CommandSafety.MUTATING})
    view = app.catalog_view
    view.selected_proto, view.selected_cmd = spec, cmd
    view.param_vars = {"rate_hz": tk.StringVar(value="5")}

    asked = []
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: asked.append(a) or False)
    view._transmit_command()
    assert asked and "mutating" in asked[0][1]
    assert app.tx_bytes_count == 0

    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    view._transmit_command()
    assert app.tx_bytes_count > 0


def test_read_only_toolbar_option_blocks_commands(app) -> None:
    spec = _select_protocol(app, "binary_sensor_node")
    app.toolbar.port_var.set("virtual")
    app.toolbar.read_only_var.set(True)
    app.toolbar._toggle_connection()
    _wait(app, lambda: app.toolbar.is_connected)
    assert "[read-only]" in app.status_text_var.get()
    app._handle_send(spec, "set_sampling_rate", {"rate_hz": 5})
    _wait(app, lambda: "failed" in app.status_text_var.get())
    assert "read-only" in app.status_text_var.get()
