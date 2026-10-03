"""Main Native Desktop GUI Application for OmniUART."""

from __future__ import annotations

import logging
import os
import queue
import tkinter as tk
from concurrent.futures import Future
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional, Union

from omniuart.core.background import VIRTUAL_PORT, BackgroundDevice
from omniuart.core.catalog import CatalogManager
from omniuart.core.codec import CodecError
from omniuart.core.models import ProtocolSpec, ScriptSpec, SerialConfig
from omniuart.core.session import Exchange, ExchangeStatus
from omniuart.desktop.views import (
    AutomationScriptRunnerView,
    CommandCatalogView,
    CommsStreamerView,
    ConnectionToolbar,
    DashboardView,
    TelemetryPlotterView,
    build_frame_payload,
)

logger = logging.getLogger(__name__)


class OmniUARTDesktopApp(tk.Tk):
    """Native Desktop GUI Application for OmniUART."""

    def __init__(self, catalog: Optional[CatalogManager] = None) -> None:
        super().__init__()
        self.title("⚡ OmniUART - Universal Schema-Driven Serial Protocol Desktop Workspace")
        self.geometry("1180x780")
        self.minsize(900, 600)

        # Configure modern dark TTK theme styles
        self._apply_dark_theme()

        self.catalog = catalog or CatalogManager()
        self.connection_config: Dict[str, Any] = {"connected": False}
        self.tx_bytes_count = 0
        self.rx_bytes_count = 0
        self.device = BackgroundDevice()
        self._events: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._pump_id: Optional[str] = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Physical serial connection header bar
        self.toolbar = ConnectionToolbar(
            self,
            on_connect_toggle=self._on_connection_change,
            catalog=self.catalog,
            on_protocol_change=self._on_global_protocol_change,
        )
        self.toolbar.pack(fill=tk.X, side=tk.TOP)

        # Separator line
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Main Workspace Notebook Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 1. Dashboard Tab
        self.dashboard_view = DashboardView(self.notebook, self.catalog)
        self.notebook.add(self.dashboard_view, text=" 📊 Dashboard ")

        # 2. Command Catalog & Builder Tab
        self.catalog_view = CommandCatalogView(self.notebook, self.catalog, on_transmit=self._handle_send)
        self.notebook.add(self.catalog_view, text=" 📜 Command Catalog ")

        # 3. Live Telemetry Plotter Tab
        self.plotter_view = TelemetryPlotterView(self.notebook, catalog=self.catalog, on_poll=self._handle_poll)
        self.notebook.add(self.plotter_view, text=" 📈 Telemetry Plotter ")

        # 4. Automation Script Runner Tab
        self.script_view = AutomationScriptRunnerView(self.notebook, self.catalog, on_run=self._handle_run_script)
        self.notebook.add(self.script_view, text=" 🤖 Script Runner ")

        # 5. Raw Comms Streamer Tab
        self.comms_view = CommsStreamerView(self.notebook, on_transmit=self._handle_raw)
        self.notebook.add(self.comms_view, text=" 📡 Comms Streamer ")

        # Status Bar at bottom
        self.statusbar = ttk.Frame(self, padding=(8, 4))
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_text_var = tk.StringVar(value="Ready. Select a command or run a script.")
        ttk.Label(self.statusbar, textvariable=self.status_text_var, font=("Segoe UI", 8)).pack(side=tk.LEFT)

        ttk.Label(self.statusbar, text="OmniUART Native Desktop", font=("Segoe UI", 8), foreground="#64748b").pack(
            side=tk.RIGHT
        )
        self._pump()

    def _apply_dark_theme(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        bg_color = "#0f172a"
        card_bg = "#1e293b"
        fg_color = "#f8fafc"
        accent_color = "#38bdf8"
        border_color = "#334155"

        self.configure(bg=bg_color)

        style.configure(".", background=bg_color, foreground=fg_color, font=("Segoe UI", 9))
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=card_bg, foreground=fg_color, bordercolor=border_color)
        style.configure("TLabelframe.Label", background=card_bg, foreground=accent_color, font=("Segoe UI", 9, "bold"))
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        style.configure("TButton", background="#3b82f6", foreground="#ffffff", font=("Segoe UI", 9, "bold"), padding=5)
        style.map("TButton", background=[("active", "#2563eb"), ("disabled", "#475569")])
        style.configure("TCombobox", fieldbackground="#1e293b", background="#334155", foreground=fg_color)
        style.configure("TEntry", fieldbackground="#1e293b", foreground=fg_color)
        style.configure("TNotebook", background=bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background="#1e293b", foreground="#94a3b8", padding=[12, 6], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#0284c7")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview", background="#1e293b", foreground=fg_color, fieldbackground="#1e293b", rowheight=24)
        style.configure("Treeview.Heading", background="#0f172a", foreground=accent_color, font=("Segoe UI", 9, "bold"))

    # ------------------------------------------------------------------ thread hand-off
    def _post(self, callback: Callable[[], None]) -> None:
        """Queue ``callback`` to run on the Tk thread; safe to call from the device thread."""
        self._events.put(callback)

    def _pump(self) -> None:
        try:
            while True:
                self._events.get_nowait()()
        except queue.Empty:
            pass
        except Exception:  # noqa: BLE001 - one bad callback must not stop the pump
            logger.exception("Error in GUI event callback")
        try:
            self._pump_id = self.after(40, self._pump)
        except tk.TclError:  # window destroyed
            self._pump_id = None

    def _watch(self, future: "Future[Any]", on_done: Callable[[Future], None]) -> None:
        future.add_done_callback(lambda f: self._post(lambda: on_done(f)))

    def destroy(self) -> None:
        if self._pump_id is not None:
            try:
                self.after_cancel(self._pump_id)
            except tk.TclError:
                pass
            self._pump_id = None
        self.device.close()
        super().destroy()

    def _on_close(self) -> None:
        self.destroy()

    # ------------------------------------------------------------------ connection
    def _serial_config(self, config: Dict[str, Any]) -> SerialConfig:
        return SerialConfig(
            baudrate=config["baudrate"],
            bytesize=config["databits"],
            parity=str(config["parity"]).lower(),
            stopbits=config["stopbits"],
        )

    def _on_connection_change(self, config: Dict[str, Any]) -> None:
        """Open or close the real link; the toolbar shows the outcome, never the intent."""
        if not config.get("connected"):
            self.status_text_var.set("Disconnecting...")
            self._watch(self.device.disconnect(), lambda f: self._connection_done(False, config, f))
            return
        self.status_text_var.set(f"Connecting to {config['port']}...")
        try:
            serial_config = None if config["port"] == VIRTUAL_PORT else self._serial_config(config)
            future = self.device.connect(config["port"], config["baudrate"], serial_config, config["rts"], config["dtr"])
        except Exception as exc:  # noqa: BLE001 - invalid serial settings
            self.toolbar.set_connected(False)
            self._report_error("Connect failed", exc)
            return
        self._watch(future, lambda f: self._connection_done(True, config, f))

    def _connection_done(self, wanted: bool, config: Dict[str, Any], future: Future) -> None:
        error = future.exception()
        if wanted and error is None:
            self.connection_config = config
            label = "simulated device" if config["port"] == VIRTUAL_PORT else f"{config['port']} @ {config['baudrate']}"
            self.toolbar.set_connected(True, label)
            self.status_text_var.set(f"Connected to {label}" + (" (simulation, not real hardware)" if config["port"] == VIRTUAL_PORT else ""))
            logger.info("Serial connection opened: %s", config["port"])
        elif wanted:
            self.connection_config = {"connected": False}
            self.toolbar.set_connected(False)
            self._report_error(f"Could not open {config['port']}", error)
        else:
            self.connection_config = {"connected": False}
            self.toolbar.set_connected(False)
            self.status_text_var.set("Disconnected")
            if error is not None:
                self._report_error("Error while closing the port", error)

    def _report_error(self, title: str, error: Optional[BaseException]) -> None:
        text = f"{type(error).__name__}: {error}" if error else title
        self.status_text_var.set(f"{title}: {text}")
        self.comms_view.log("ERR", b"", title, decoded=text)
        if not self.winfo_viewable() or os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("HEADLESS") == "1":
            return
        messagebox.showerror(title, text)

    def _on_global_protocol_change(self, proto_name: str) -> None:
        """Propagate active protocol selection across all workspace tabs."""
        self.dashboard_view.proto_var.set(proto_name)
        self.dashboard_view.refresh_data()
        self.catalog_view.proto_filter_var.set(proto_name)
        self.catalog_view._populate_tree()
        self.status_text_var.set(f"Global active protocol set to: '{proto_name}'")

    def _active_spec(self) -> Optional[ProtocolSpec]:
        name = self.toolbar.proto_var.get()
        if not name or name == "None":
            return None
        for entry in self.catalog.catalog_summary().get("protocols", []):
            if entry.get("name") == name:
                return self.catalog.get_protocol(entry.get("filename", ""))
        return None

    # ------------------------------------------------------------------ traffic
    def _require_link(self) -> bool:
        if self.device.connected:
            return True
        self.status_text_var.set("Not connected. Connect a serial port or the virtual device first.")
        return False

    def _handle_send(self, spec: ProtocolSpec, command: str, params: Dict[str, Any], label: str = "") -> Optional["Future[Exchange]"]:
        """Encode, transmit and decode ``command``; log what really went out and what really came back."""
        if not self._require_link():
            return None
        label = label or command
        try:
            request = build_frame_payload(spec, spec.get_command(command), params)  # type: ignore[arg-type]
            future = self.device.send(spec, command, params)
        except CodecError as exc:
            self._report_error(f"Cannot send '{command}'", exc)
            return None
        self.tx_bytes_count += len(request)
        self.comms_view.log("TX", request, label, decoded=", ".join(f"{k}={v}" for k, v in params.items()))
        self._watch(future, lambda f: self._send_done(label, f))
        return future

    def _send_done(self, label: str, future: Future) -> None:
        if future.cancelled():
            return
        error = future.exception()
        if error is not None:
            self._report_error(f"'{label}' failed", error)
            return
        exchange: Exchange = future.result()
        self.rx_bytes_count += len(exchange.response_bytes)
        if exchange.response_bytes:
            fields = exchange.fields
            decoded = ", ".join(f"{k}={v}" for k, v in fields.items()) if exchange.ok else (exchange.error or "")
            self.comms_view.log("RX" if exchange.ok else "ERR", exchange.response_bytes, label, decoded=decoded)
        if exchange.status is not ExchangeStatus.OK:
            self.comms_view.log("ERR", b"", label, decoded=f"{exchange.status.value}: {exchange.error}")
            self.status_text_var.set(f"'{label}': {exchange.status.value} - {exchange.error}")
            return
        for frame in exchange.frames:
            if frame.ok:
                self.plotter_view.push_fields(frame.fields)
        if exchange.response is not None and exchange.response not in exchange.frames:
            self.plotter_view.push_fields(exchange.response.fields)
        self.status_text_var.set(f"'{label}' answered in {exchange.latency_ms:.0f} ms")

    def _handle_poll(self, spec: ProtocolSpec, command: str) -> Optional["Future[Exchange]"]:
        return self._handle_send(spec, command, {}, label=f"Poll: {command}")

    def _handle_raw(self, label: str, data: bytes) -> None:
        """Send user-typed bytes unmodified and show whatever comes back."""
        if not self._require_link():
            return
        future = self.device.send_raw(data, spec=self._active_spec())
        self.tx_bytes_count += len(data)
        self.comms_view.log("TX", data, label)
        self._watch(future, lambda f: self._raw_done(label, f))

    def _raw_done(self, label: str, future: Future) -> None:
        error = future.exception()
        if error is not None:
            self._report_error(f"'{label}' failed", error)
            return
        reply: bytes = future.result()
        self.rx_bytes_count += len(reply)
        if reply:
            self.comms_view.log("RX", reply, label)
            self.status_text_var.set(f"'{label}': {len(reply)} bytes received")
        else:
            self.status_text_var.set(f"'{label}': no reply")

    def _handle_run_script(
        self,
        script: ScriptSpec,
        spec: ProtocolSpec,
        on_step: Callable[[Any], None],
        on_done: Callable[[Any, Optional[BaseException], bool], None],
    ) -> Optional["Future[Any]"]:
        """Run ``script`` on the open link with the shared runner; callbacks arrive on the Tk thread."""
        if not self._require_link():
            return None
        future = self.device.run_script(script, spec, on_step=lambda r: self._post(lambda: on_step(r)))

        def finished(f: Future) -> None:
            if f.cancelled():
                on_done(None, None, True)
            else:
                error = f.exception()
                on_done(None if error else f.result(), error, False)

        self._watch(future, finished)
        return future


def launch_native_desktop_app(
    protocol_dirs: Optional[List[Union[str, Any]]] = None,
    script_dirs: Optional[List[Union[str, Any]]] = None,
) -> None:
    """Launch native Tkinter desktop application."""
    catalog = CatalogManager(protocol_dirs=protocol_dirs, script_dirs=script_dirs)
    try:
        app = OmniUARTDesktopApp(catalog=catalog)
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("HEADLESS") == "1":
            app.update()
            app.destroy()
            return
        app.mainloop()
    except Exception as e:
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("HEADLESS") == "1":
            return
        raise e


if __name__ == "__main__":
    launch_native_desktop_app()
