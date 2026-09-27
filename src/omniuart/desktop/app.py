"""Main Native Desktop GUI Application for OmniUART."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional, Union

from omniuart.core.catalog import CatalogManager
from omniuart.desktop.views import (
    AutomationScriptRunnerView,
    CommandCatalogView,
    CommsStreamerView,
    ConnectionToolbar,
    DashboardView,
    TelemetryPlotterView,
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

        # Physical serial connection header bar
        self.toolbar = ConnectionToolbar(self, on_connect_toggle=self._on_connection_change)
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
        self.catalog_view = CommandCatalogView(self.notebook, self.catalog, on_transmit=self._handle_transmit)
        self.notebook.add(self.catalog_view, text=" 📜 Command Catalog ")

        # 3. Live Telemetry Plotter Tab
        self.plotter_view = TelemetryPlotterView(self.notebook)
        self.notebook.add(self.plotter_view, text=" 📈 Telemetry Plotter ")

        # 4. Automation Script Runner Tab
        self.script_view = AutomationScriptRunnerView(self.notebook, self.catalog, on_transmit=self._handle_transmit)
        self.notebook.add(self.script_view, text=" 🤖 Script Runner ")

        # 5. Raw Comms Streamer Tab
        self.comms_view = CommsStreamerView(self.notebook, on_transmit=self._handle_transmit)
        self.notebook.add(self.comms_view, text=" 📡 Comms Streamer ")

        # Status Bar at bottom
        self.statusbar = ttk.Frame(self, padding=(8, 4))
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_text_var = tk.StringVar(value="Ready. Select a command or run a script.")
        ttk.Label(self.statusbar, textvariable=self.status_text_var, font=("Segoe UI", 8)).pack(side=tk.LEFT)

        ttk.Label(self.statusbar, text="OmniUART Native Desktop v1.4.0", font=("Segoe UI", 8), foreground="#64748b").pack(
            side=tk.RIGHT
        )

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

    def _on_connection_change(self, config: Dict[str, Any]) -> None:
        self.connection_config = config
        state_str = "Connected to " + config["port"] if config["connected"] else "Disconnected"
        self.status_text_var.set(f"Physical Serial Status: {state_str}")
        logger.info("Serial connection updated: %s", config)

    def _handle_transmit(self, label: str, raw_bytes: bytes) -> None:
        self.tx_bytes_count += len(raw_bytes)
        self.comms_view.log("TX", raw_bytes, label)
        self.status_text_var.set(f"Transmitted '{label}' ({len(raw_bytes)} bytes)")


def launch_native_desktop_app(
    protocol_dirs: Optional[List[Union[str, Any]]] = None,
    script_dirs: Optional[List[Union[str, Any]]] = None,
) -> None:
    """Launch native Tkinter desktop application."""
    catalog = CatalogManager(protocol_dirs=protocol_dirs, script_dirs=script_dirs)
    app = OmniUARTDesktopApp(catalog=catalog)
    app.mainloop()


if __name__ == "__main__":
    launch_native_desktop_app()
