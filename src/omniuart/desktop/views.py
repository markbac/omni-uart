"""Tkinter Desktop View Components for OmniUART Native Desktop GUI Application."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from concurrent.futures import Future
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from omniuart.core.catalog import CatalogManager
from omniuart.core.background import VIRTUAL_PORT, is_safe_poll_command
from omniuart.core.codec import FrameCodec
from omniuart.core.models import CommandSpec, ProtocolSpec
from omniuart.core.transport import list_available_ports


def build_frame_payload(spec: ProtocolSpec, cmd: CommandSpec, params: Dict[str, Any]) -> bytes:
    """Build the raw wire frame for a command using the shared schema-driven codec.

    Raises :class:`omniuart.core.codec.CodecError` for missing, unknown, out-of-range or
    otherwise invalid parameters instead of transmitting a guessed value.
    """
    return FrameCodec(spec).encode_command(cmd, params)


class ConnectionToolbar(ttk.Frame):
    """Header toolbar for physical serial connection configuration and status."""

    def __init__(
        self,
        parent: tk.Widget,
        on_connect_toggle: Callable[[Dict[str, Any]], None],
        catalog: Optional[CatalogManager] = None,
        on_protocol_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent, padding=(10, 8, 10, 8))
        self.on_connect_toggle = on_connect_toggle
        self.catalog = catalog
        self.on_protocol_change = on_protocol_change
        self.is_connected = False

        # Global Active Protocol selector
        ttk.Label(self, text="Protocol:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(4, 2))
        self.proto_var = tk.StringVar(value="None")
        self.proto_combo = ttk.Combobox(self, textvariable=self.proto_var, state="readonly", width=18)
        self.proto_combo.pack(side=tk.LEFT, padx=(0, 6))
        self.proto_combo.bind("<<ComboboxSelected>>", lambda e: self._on_proto_select())
        self._refresh_protocols()

        # Physical serial settings widgets
        ttk.Label(self, text="Serial Port:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=4)
        self.port_var = tk.StringVar(value=VIRTUAL_PORT)
        self.port_combo = ttk.Combobox(self, textvariable=self.port_var, values=[VIRTUAL_PORT], width=14)
        self.port_combo.pack(side=tk.LEFT, padx=2)

        self.refresh_btn = ttk.Button(self, text="🔄", width=3, command=self._refresh_ports)
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 4))
        self._refresh_ports()

        ttk.Label(self, text="Baud Rate:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=4)
        self.baud_var = tk.StringVar(value="115200")
        self.baud_combo = ttk.Combobox(
            self,
            textvariable=self.baud_var,
            values=["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"],
            width=10,
        )
        self.baud_combo.pack(side=tk.LEFT, padx=4)

        ttk.Label(self, text="Data Bits:").pack(side=tk.LEFT, padx=4)
        self.databits_var = tk.StringVar(value="8")
        self.databits_combo = ttk.Combobox(self, textvariable=self.databits_var, values=["5", "6", "7", "8"], width=4)
        self.databits_combo.pack(side=tk.LEFT, padx=4)

        ttk.Label(self, text="Parity:").pack(side=tk.LEFT, padx=4)
        self.parity_var = tk.StringVar(value="None")
        self.parity_combo = ttk.Combobox(
            self, textvariable=self.parity_var, values=["None", "Even", "Odd", "Mark", "Space"], width=6
        )
        self.parity_combo.pack(side=tk.LEFT, padx=4)

        ttk.Label(self, text="Stop Bits:").pack(side=tk.LEFT, padx=4)
        self.stopbits_var = tk.StringVar(value="1")
        self.stopbits_combo = ttk.Combobox(self, textvariable=self.stopbits_var, values=["1", "1.5", "2"], width=4)
        self.stopbits_combo.pack(side=tk.LEFT, padx=4)

        self.rts_var = tk.BooleanVar(value=True)
        self.rts_check = ttk.Checkbutton(self, text="RTS", variable=self.rts_var)
        self.rts_check.pack(side=tk.LEFT, padx=4)

        self.dtr_var = tk.BooleanVar(value=True)
        self.dtr_check = ttk.Checkbutton(self, text="DTR", variable=self.dtr_var)
        self.dtr_check.pack(side=tk.LEFT, padx=4)

        self.connect_btn = ttk.Button(self, text="⚡ Connect", command=self._toggle_connection, width=12)
        self.connect_btn.pack(side=tk.LEFT, padx=10)

        self.status_label = ttk.Label(
            self, text="● Disconnected", font=("Segoe UI", 9, "bold"), foreground="#dc2626"
        )
        self.status_label.pack(side=tk.LEFT, padx=10)

    def _refresh_protocols(self) -> None:
        """Populate global active protocol selector from catalog manager."""
        if self.catalog:
            summary = self.catalog.catalog_summary()
            names = ["None"] + [p.get("name", "") for p in summary.get("protocols", [])]
            self.proto_combo["values"] = names
        else:
            self.proto_combo["values"] = ["None"]

    def _on_proto_select(self) -> None:
        """Auto-configure physical serial connection parameters when active protocol changes."""
        selected_name = self.proto_var.get()
        if self.catalog and selected_name != "None":
            summary = self.catalog.catalog_summary()
            for p in summary.get("protocols", []):
                if p.get("name") == selected_name:
                    spec = self.catalog.get_protocol(p.get("filename", ""))
                    if spec and hasattr(spec, "serial_config"):
                        sc = spec.serial_config
                        self.baud_var.set(str(sc.baudrate))
                        self.databits_var.set(str(sc.bytesize))
                        parity_str = str(sc.parity).capitalize()
                        if parity_str in ["None", "Even", "Odd", "Mark", "Space"]:
                            self.parity_var.set(parity_str)
                        self.stopbits_var.set(str(sc.stopbits))
                    break
        if self.on_protocol_change:
            self.on_protocol_change(selected_name)

    def _refresh_ports(self) -> None:
        """Scan available physical COM / serial ports and update combobox values."""
        try:
            detected = [p["device"] for p in list_available_ports()]
        except Exception:  # noqa: BLE001 - enumeration can fail on locked-down systems
            detected = []
        # Only ports that exist are offered, plus the explicitly simulated virtual device.
        port_names = detected + [VIRTUAL_PORT]
        self.port_combo["values"] = port_names
        if self.port_var.get() not in port_names and not self.is_connected:
            self.port_var.set(port_names[0])

    def _toggle_connection(self) -> None:
        """Ask the application to connect or disconnect; the button changes only once it reports back."""
        if self.is_connected:
            config: Dict[str, Any] = {"connected": False}
        else:
            try:
                config = {
                    "connected": True,
                    "port": self.port_var.get().strip(),
                    "baudrate": int(self.baud_var.get()),
                    "databits": int(self.databits_var.get()),
                    "parity": self.parity_var.get(),
                    "stopbits": float(self.stopbits_var.get()),
                    "rts": self.rts_var.get(),
                    "dtr": self.dtr_var.get(),
                }
            except ValueError as exc:
                messagebox.showerror("Connection settings", f"Invalid serial setting: {exc}")
                return
            if not config["port"]:
                messagebox.showerror("Connection settings", "Choose a serial port or the virtual device.")
                return
        self.connect_btn.config(state=tk.DISABLED)
        self.on_connect_toggle(config)

    def set_connected(self, connected: bool, detail: str = "") -> None:
        """Reflect the real link state reported by the application."""
        self.is_connected = connected
        self.connect_btn.config(state=tk.NORMAL)
        if connected:
            self.connect_btn.config(text="🔌 Disconnect")
            self.status_label.config(text=f"● Connected ({detail})", foreground="#16a34a")
        else:
            self.connect_btn.config(text="⚡ Connect")
            self.status_label.config(text="● Disconnected", foreground="#dc2626")


class DashboardView(ttk.Frame):
    """Dashboard tab showing overview metrics, serial status, and loaded protocols."""

    def __init__(self, parent: tk.Widget, catalog: CatalogManager) -> None:
        super().__init__(parent, padding=16)
        self.catalog = catalog

        # Protocol Selector Bar
        proto_bar = ttk.Frame(self)
        proto_bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(proto_bar, text="Active Protocol View:", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        self.proto_var = tk.StringVar(value="None")
        self.proto_combo = ttk.Combobox(proto_bar, textvariable=self.proto_var, state="readonly", width=35)
        self.proto_combo.pack(side=tk.LEFT)
        self.proto_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_data())

        # Metrics cards frame
        self.cards_frame = ttk.Frame(self)
        self.cards_frame.pack(fill=tk.X, pady=10)

        # Overview section
        overview_frame = ttk.LabelFrame(self, text=" Protocol Schemas ", padding=12)
        overview_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        tree_columns = ("id", "name", "version", "transport", "commands")
        self.tree = ttk.Treeview(overview_frame, columns=tree_columns, show="headings", height=10)
        self.tree.heading("id", text="ID / File")
        self.tree.heading("name", text="Protocol Name")
        self.tree.heading("version", text="Version")
        self.tree.heading("transport", text="Transport")
        self.tree.heading("commands", text="Total Commands")

        self.tree.column("id", width=140)
        self.tree.column("name", width=220)
        self.tree.column("version", width=80)
        self.tree.column("transport", width=100)
        self.tree.column("commands", width=120)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.refresh_data()

    def _create_card(self, parent: tk.Widget, title: str, value: str, color: str, col: int) -> None:
        card = tk.Frame(parent, bg="#1e293b", relief=tk.RAISED, bd=1, padx=16, pady=12)
        card.grid(row=0, column=col, sticky="ew", padx=8)
        parent.columnconfigure(col, weight=1)

        tk.Label(card, text=title, font=("Segoe UI", 9, "bold"), fg="#94a3b8", bg="#1e293b").pack(anchor="w")
        tk.Label(card, text=value, font=("Segoe UI", 16, "bold"), fg="#f8fafc", bg="#1e293b").pack(anchor="w", pady=(4, 0))

    def refresh_data(self) -> None:
        """Populate protocol schema treeview and cards based on active selection."""
        for child in self.cards_frame.winfo_children():
            child.destroy()

        for item in self.tree.get_children():
            self.tree.delete(item)

        summary = self.catalog.catalog_summary()
        protocols = summary.get("protocols", [])

        # Update combo options
        proto_names = ["None", "All Protocols"] + [p.get("name", "") for p in protocols]
        self.proto_combo["values"] = proto_names

        selected = self.proto_var.get()

        if selected == "None":
            self._create_card(self.cards_frame, "Active Protocol", "None", "#64748b", 0)
            self._create_card(self.cards_frame, "Available Commands", "0", "#64748b", 1)
            self._create_card(self.cards_frame, "Baud Rate", "N/A", "#64748b", 2)
            self._create_card(self.cards_frame, "Schema Version", "N/A", "#64748b", 3)
        elif selected == "All Protocols":
            protocols_count = summary.get("protocols_found", 0)
            scripts_count = summary.get("scripts_found", 0)
            self._create_card(self.cards_frame, "Loaded Protocols", str(protocols_count), "#2563eb", 0)
            self._create_card(self.cards_frame, "Automation Scripts", str(scripts_count), "#7c3aed", 1)
            self._create_card(self.cards_frame, "TX Bytes Sent", "0 B", "#059669", 2)
            self._create_card(self.cards_frame, "RX Bytes Received", "0 B", "#d97706", 3)

            for p in protocols:
                self.tree.insert("", tk.END, values=(p.get("filename", ""), p.get("name", ""), p.get("version", ""), "UART", p.get("commands_count", 0)))
        else:
            filtered = [p for p in protocols if p.get("name") == selected]
            p_obj = filtered[0] if filtered else {}
            cmd_count = p_obj.get("commands_count", 0)
            baud = p_obj.get("baudrate", 115200)

            self._create_card(self.cards_frame, "Selected Protocol", selected[:18], "#2563eb", 0)
            self._create_card(self.cards_frame, "Available Commands", str(cmd_count), "#7c3aed", 1)
            self._create_card(self.cards_frame, "Baud Rate", f"{baud} bps", "#059669", 2)
            self._create_card(self.cards_frame, "Schema Version", str(p_obj.get("version", "1.0")), "#d97706", 3)

            for p in filtered:
                self.tree.insert("", tk.END, values=(p.get("filename", ""), p.get("name", ""), p.get("version", ""), "UART", p.get("commands_count", 0)))


class CommandCatalogView(ttk.Frame):
    """Command catalog browser and dynamic parameter builder tab."""

    def __init__(
        self,
        parent: tk.Widget,
        catalog: CatalogManager,
        on_transmit: Callable[[ProtocolSpec, str, Dict[str, Any]], None],
    ) -> None:
        super().__init__(parent, padding=12)
        self.catalog = catalog
        self.on_transmit = on_transmit
        self.selected_cmd: Optional[CommandSpec] = None
        self.selected_proto: Optional[ProtocolSpec] = None
        self.param_vars: Dict[str, Any] = {}

        # Left/Right PanedWindow
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left pane: Command Treeview & Filter
        left_frame = ttk.Frame(paned, padding=8)
        paned.add(left_frame, weight=1)

        # Protocol Filter Combo
        ttk.Label(left_frame, text="Active Protocol Filter:").pack(anchor="w")
        self.proto_filter_var = tk.StringVar(value="None")
        self.proto_filter_combo = ttk.Combobox(left_frame, textvariable=self.proto_filter_var, state="readonly")
        self.proto_filter_combo.pack(fill=tk.X, pady=(0, 6))
        self.proto_filter_combo.bind("<<ComboboxSelected>>", lambda e: self._populate_tree())

        ttk.Label(left_frame, text="Filter Commands:").pack(anchor="w")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *args: self._populate_tree())
        ttk.Entry(left_frame, textvariable=self.filter_var).pack(fill=tk.X, pady=(0, 8))

        self.tree = ttk.Treeview(left_frame, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_command)

        # Right pane: Dynamic Form & Transmitter
        right_frame = ttk.LabelFrame(paned, text=" Command Builder & Form Parameters ", padding=12)
        paned.add(right_frame, weight=2)

        self.cmd_title_label = ttk.Label(right_frame, text="No Active Protocol Selected", font=("Segoe UI", 11, "bold"))
        self.cmd_title_label.pack(anchor="w", pady=(0, 4))

        self.cmd_desc_label = ttk.Label(right_frame, text="Select an active protocol from top header to view available commands.", wraplength=450, foreground="#64748b")
        self.cmd_desc_label.pack(anchor="w", pady=(0, 8))

        # Dynamic params container
        self.params_container = ttk.Frame(right_frame)
        self.params_container.pack(fill=tk.BOTH, expand=True, pady=8)

        # Output preview frame
        preview_frame = ttk.LabelFrame(right_frame, text=" Frame Payload Preview ", padding=8)
        preview_frame.pack(fill=tk.X, pady=8)

        self.hex_preview_var = tk.StringVar(value="<No Command Selected>")
        ttk.Label(preview_frame, textvariable=self.hex_preview_var, font=("Consolas", 10, "bold"), foreground="#2563eb").pack(
            anchor="w"
        )

        # Transmit button
        self.tx_btn = ttk.Button(right_frame, text="🚀 Transmit Command", command=self._transmit_command, state=tk.DISABLED)
        self.tx_btn.pack(anchor="e", pady=4)

        self._populate_tree()

    def _populate_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        filter_text = self.filter_var.get().lower()
        selected_proto_name = self.proto_filter_var.get()

        summary = self.catalog.catalog_summary()
        protocols = summary.get("protocols", [])

        # Update protocol combo values
        proto_names = ["None", "All Protocols"] + [p.get("name", "") for p in protocols]
        self.proto_filter_combo["values"] = proto_names

        if selected_proto_name == "None":
            self.cmd_title_label.config(text="No Active Protocol Selected")
            self.cmd_desc_label.config(text="Select an active protocol from top header to view available commands.")
            return

        for p in protocols:
            p_name = p.get("name", "")
            if selected_proto_name != "All Protocols" and p_name != selected_proto_name:
                continue

            filename = p.get("filename", "")
            spec = self.catalog.get_protocol(filename)
            if not spec:
                continue

            proto_node = self.tree.insert("", tk.END, text=f"📦 {spec.metadata.name} ({filename})", open=True)

            # Group commands by tags
            tag_groups: Dict[str, List[CommandSpec]] = {}
            for cmd in spec.commands:
                if filter_text and filter_text not in cmd.name.lower() and filter_text not in str(cmd.id).lower():
                    continue
                tag = cmd.tags[0] if cmd.tags else "General"
                tag_groups.setdefault(tag, []).append(cmd)

            for tag, cmds in tag_groups.items():
                tag_node = self.tree.insert(proto_node, tk.END, text=f"🏷️ {tag}", open=True)
                for cmd in cmds:
                    disc_val = getattr(cmd, "discriminator", None)
                    disc_badge = f" [Tag: {disc_val}]" if disc_val is not None else ""
                    cmd_id_str = f"0x{cmd.id:02X}" if isinstance(cmd.id, int) else str(cmd.id)
                    self.tree.insert(
                        tag_node,
                        tk.END,
                        text=f"⚡ {cmd.name} ({cmd_id_str}){disc_badge}",
                        values=(filename, str(cmd.id)),
                    )

    def _on_select_command(self, event: tk.Event) -> None:
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0])
        values = item.get("values", [])
        if not values or len(values) < 2:
            return

        proto_filename, cmd_id_raw = values[0], values[1]
        spec = self.catalog.get_protocol(proto_filename)
        if not spec:
            return

        cmd = next((c for c in spec.commands if str(c.id) == cmd_id_raw or c.id == cmd_id_raw), None)
        if not cmd:
            return

        self.selected_cmd = cmd
        self.selected_proto = spec

        # Update labels
        disc_val = getattr(cmd, "discriminator", None)
        if disc_val is not None:
            disc_text = f" | Discriminator: 0x{disc_val:02X}" if isinstance(disc_val, int) else f" | Discriminator: {disc_val}"
        else:
            disc_text = ""
        cmd_id_str = f"0x{cmd.id:02X}" if isinstance(cmd.id, int) else str(cmd.id)
        self.cmd_title_label.config(text=f"{cmd.name} (ID: {cmd_id_str}{disc_text})")
        self.cmd_desc_label.config(text=cmd.description or "No description provided.")

        # Rebuild dynamic form fields
        for widget in self.params_container.winfo_children():
            widget.destroy()

        self.param_vars.clear()

        if not cmd.parameters:
            ttk.Label(self.params_container, text="This command takes no parameters.", font=("Segoe UI", 9, "italic")).pack(anchor="w")
        else:
            for param in cmd.parameters:
                row = ttk.Frame(self.params_container)
                row.pack(fill=tk.X, pady=4)

                unit_str = f" [{param.unit}]" if param.unit else ""
                label_text = f"{param.name}{unit_str}:"
                ttk.Label(row, text=label_text, width=20, anchor="w").pack(side=tk.LEFT)

                options = getattr(param, "options", None)
                if options:
                    opts_list = [str(v) for v in (options.values() if isinstance(options, dict) else options)]
                    var = tk.StringVar(value=opts_list[0] if opts_list else "")
                    combo = ttk.Combobox(row, textvariable=var, values=opts_list, width=20)
                    combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    var.trace_add("write", lambda *args: self._update_preview())
                    self.param_vars[param.name] = var
                elif param.type.value in ("uint8", "uint16", "uint32", "int8", "int16", "int32", "float", "double", "float32", "float64"):
                    default_val = str(param.default if param.default is not None else "0")
                    var = tk.StringVar(value=default_val)
                    entry = ttk.Entry(row, textvariable=var, width=20)
                    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    var.trace_add("write", lambda *args: self._update_preview())
                    self.param_vars[param.name] = var
                elif param.type.value == "bool":
                    var = tk.BooleanVar(value=bool(param.default))
                    chk = ttk.Checkbutton(row, text="Enabled", variable=var, command=self._update_preview)
                    chk.pack(side=tk.LEFT)
                    self.param_vars[param.name] = var
                else:
                    var = tk.StringVar(value=str(param.default if param.default is not None else ""))
                    entry = ttk.Entry(row, textvariable=var, width=20)
                    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    var.trace_add("write", lambda *args: self._update_preview())
                    self.param_vars[param.name] = var

        self.tx_btn.config(state=tk.NORMAL)
        self._update_preview()

    def _update_preview(self) -> None:
        if not self.selected_cmd or not self.selected_proto:
            return
        param_dict = {}
        for k, var in self.param_vars.items():
            param_dict[k] = var.get()
        try:
            raw_bytes = build_frame_payload(self.selected_proto, self.selected_cmd, param_dict)
            self.hex_preview_var.set(" ".join(f"{b:02X}" for b in raw_bytes))
        except Exception as e:
            self.hex_preview_var.set(f"Invalid Parameters: {e}")

    def _transmit_command(self) -> None:
        if not self.selected_cmd or not self.selected_proto:
            return
        param_dict = {}
        for k, var in self.param_vars.items():
            param_dict[k] = var.get()

        try:
            build_frame_payload(self.selected_proto, self.selected_cmd, param_dict)  # validate before sending
        except Exception as e:
            messagebox.showerror("Transmission Error", f"Invalid parameters: {e}")
            return
        self.on_transmit(self.selected_proto, self.selected_cmd.name, param_dict)


class TelemetryPlotterView(ttk.Frame):
    """Line chart of numeric fields from decoded RX frames, with optional polling of safe commands.

    Nothing is plotted from transmitted bytes or guessed from raw data: only values the protocol codec
    decoded from a valid device response reach the chart.
    """

    MAX_POINTS = 100

    def __init__(
        self,
        parent: tk.Widget,
        catalog: Optional[CatalogManager] = None,
        on_poll: Optional[Callable[[ProtocolSpec, str], Optional["Future[Any]"]]] = None,
    ) -> None:
        super().__init__(parent, padding=12)
        self.catalog = catalog
        self.on_poll = on_poll
        self.channel_1_points: List[float] = []
        self.channel_2_points: List[float] = []
        self.channel_names: List[str] = ["", ""]
        self.is_running = True
        self.is_polling = False
        self.poll_timer_id: Optional[str] = None
        self._poll_future: Optional["Future[Any]"] = None
        self.poll_targets: Dict[str, Tuple[ProtocolSpec, str]] = {}

        toolbar1 = ttk.Frame(self)
        toolbar1.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(toolbar1, text="📈 Live Telemetry (decoded RX fields)", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        self.pause_btn = ttk.Button(toolbar1, text="Pause Plotter", command=self._toggle_plotter)
        self.pause_btn.pack(side=tk.RIGHT, padx=4)
        ttk.Button(toolbar1, text="Clear Data", command=self._clear_plotter).pack(side=tk.RIGHT, padx=4)

        toolbar2 = ttk.Frame(self)
        toolbar2.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(toolbar2, text="Poll Command:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.cmd_var = tk.StringVar()
        self.cmd_combo = ttk.Combobox(toolbar2, textvariable=self.cmd_var, state="readonly", width=34)
        self.cmd_combo.pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar2, text="Frequency:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(10, 4))
        self.interval_var = tk.StringVar(value="500 ms")
        self.interval_combo = ttk.Combobox(
            toolbar2,
            textvariable=self.interval_var,
            values=["100 ms", "200 ms", "500 ms", "1.0 s", "2.0 s", "5.0 s"],
            state="readonly",
            width=8,
        )
        self.interval_combo.pack(side=tk.LEFT, padx=2)
        self.poll_btn = ttk.Button(toolbar2, text="▶ Start Auto-Poll", command=self._toggle_auto_poll)
        self.poll_btn.pack(side=tk.LEFT, padx=8)

        ttk.Label(
            self,
            text="Only read-only commands tagged 'dashboard' with defaulted parameters can be polled. "
            "Ch1 and Ch2 are the first two numeric fields of each decoded response.",
            foreground="#64748b",
            font=("Segoe UI", 9, "italic"),
            wraplength=900,
        ).pack(anchor="w", pady=(0, 6))

        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill=tk.X, pady=(0, 8))
        self.cur_val_var = tk.StringVar(value="Ch1 (Cyan): --")
        self.ch2_val_var = tk.StringVar(value="Ch2 (Green): --")
        self.min_val_var = tk.StringVar(value="Min: --")
        self.max_val_var = tk.StringVar(value="Max: --")
        self.avg_val_var = tk.StringVar(value="Avg: --")
        for var, colour in (
            (self.cur_val_var, "#38bdf8"),
            (self.ch2_val_var, "#4ade80"),
            (self.min_val_var, "#94a3b8"),
            (self.max_val_var, "#94a3b8"),
            (self.avg_val_var, "#94a3b8"),
        ):
            ttk.Label(stats_frame, textvariable=var, font=("Consolas", 10, "bold"), foreground=colour).pack(side=tk.LEFT, padx=(0, 12))

        self.canvas = tk.Canvas(self, bg="#0f172a", highlightthickness=1, highlightbackground="#334155")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._refresh_poll_commands()
        self._draw_chart()

    def _refresh_poll_commands(self) -> None:
        """Offer only commands that are safe to repeat unattended (see ``is_safe_poll_command``)."""
        self.poll_targets = {}
        if self.catalog:
            for entry in self.catalog.catalog_summary().get("protocols", []):
                spec = self.catalog.get_protocol(entry.get("filename", ""))
                if not spec:
                    continue
                for cmd in spec.commands:
                    if is_safe_poll_command(cmd):
                        self.poll_targets[f"{spec.metadata.name}: {cmd.name}"] = (spec, cmd.name)
        labels = list(self.poll_targets)
        self.cmd_combo["values"] = labels
        if labels and self.cmd_var.get() not in self.poll_targets:
            self.cmd_var.set(labels[0])

    def _toggle_auto_poll(self) -> None:
        """Start or stop periodic polling of the selected safe command."""
        if not self.is_polling and self.cmd_var.get() not in self.poll_targets:
            messagebox.showinfo("Auto-Poll", "No pollable command is available (needs a 'dashboard' command with defaulted parameters).")
            return
        self.is_polling = not self.is_polling
        if self.is_polling:
            self.poll_btn.config(text="⏹ Stop Polling")
            self._trigger_poll()
        else:
            self.poll_btn.config(text="▶ Start Auto-Poll")
            if self.poll_timer_id:
                self.after_cancel(self.poll_timer_id)
                self.poll_timer_id = None

    @staticmethod
    def _interval_ms(text: str) -> int:
        text = text.strip()
        if text.endswith("ms"):
            return int(float(text[:-2]))
        return int(float(text.rstrip("s").strip()) * 1000)

    def _trigger_poll(self) -> None:
        if not self.is_polling:
            return
        target = self.poll_targets.get(self.cmd_var.get())
        busy = self._poll_future is not None and not self._poll_future.done()
        if target and self.on_poll and not busy:
            future = self.on_poll(target[0], target[1])
            if future is None:  # not connected: stop instead of polling a dead link
                self._toggle_auto_poll()
                return
            self._poll_future = future
        self.poll_timer_id = self.after(max(100, self._interval_ms(self.interval_var.get())), self._trigger_poll)

    def _toggle_plotter(self) -> None:
        self.is_running = not self.is_running
        self.pause_btn.config(text="Resume Plotter" if not self.is_running else "Pause Plotter")

    def _clear_plotter(self) -> None:
        self.channel_1_points = []
        self.channel_2_points = []
        self._draw_chart()

    def push_fields(self, fields: Mapping[str, Any]) -> None:
        """Plot the first two numeric fields of one decoded RX frame."""
        if not self.is_running:
            return
        numeric = [(k, float(v)) for k, v in fields.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if not numeric:
            return
        for index, points in enumerate((self.channel_1_points, self.channel_2_points)):
            if index < len(numeric):
                self.channel_names[index] = numeric[index][0]
                points.append(numeric[index][1])
                del points[: -self.MAX_POINTS]
        self._draw_chart()

    def _draw_chart(self) -> None:
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 100 or h < 100:
            return

        margin_left, margin_bottom = 70, 30
        plot_w = w - margin_left - 15
        plot_h = h - margin_bottom - 20

        if not self.channel_1_points:
            self.canvas.create_text(
                w / 2 + margin_left / 2,
                h / 2,
                text="📡 Waiting for decoded device responses...\n(Transmit a command or use '▶ Start Auto-Poll')",
                fill="#64748b",
                font=("Segoe UI", 10, "italic"),
                justify="center",
            )
            for var, label in (
                (self.cur_val_var, "Ch1 (Cyan)"),
                (self.ch2_val_var, "Ch2 (Green)"),
                (self.min_val_var, "Min"),
                (self.max_val_var, "Max"),
                (self.avg_val_var, "Avg"),
            ):
                var.set(f"{label}: --")
            return

        everything = self.channel_1_points + self.channel_2_points
        lo, hi = min(everything), max(everything)
        if hi == lo:
            lo, hi = lo - 1.0, hi + 1.0
        pad = (hi - lo) * 0.05
        lo, hi = lo - pad, hi + pad

        def y_of(value: float) -> float:
            return (20 + plot_h) - (value - lo) / (hi - lo) * plot_h

        for i in range(5):
            y = 20 + i * (plot_h / 4.0)
            self.canvas.create_line(margin_left, y, w - 15, y, fill="#1e293b", dash=(2, 4))
            self.canvas.create_text(margin_left - 8, y, text=f"{hi - i * (hi - lo) / 4.0:.4g}", fill="#64748b", font=("Consolas", 8), anchor="e")
        self.canvas.create_line(margin_left, 20 + plot_h, w - 15, 20 + plot_h, fill="#334155")
        self.canvas.create_text(
            w / 2 + margin_left / 2, h - 10, text="Decoded RX samples", fill="#64748b", font=("Segoe UI", 8, "italic")
        )

        for points, colour in ((self.channel_1_points, "#38bdf8"), (self.channel_2_points, "#4ade80")):
            if len(points) >= 2:
                step = plot_w / (len(points) - 1)
                coords: List[float] = []
                for i, val in enumerate(points):
                    coords.extend([margin_left + i * step, y_of(val)])
                self.canvas.create_line(*coords, fill=colour, width=2)
            elif points:
                self.canvas.create_oval(margin_left - 2, y_of(points[0]) - 2, margin_left + 2, y_of(points[0]) + 2, fill=colour, outline=colour)

        name1 = self.channel_names[0] or "Ch1"
        name2 = self.channel_names[1] or "Ch2"
        self.canvas.create_rectangle(w - 270, 20, w - 20, 65, fill="#1e293b", outline="#334155")
        self.canvas.create_line(w - 260, 32, w - 230, 32, fill="#38bdf8", width=2)
        self.canvas.create_text(w - 225, 32, text=f"Line 1: {name1}", fill="#f8fafc", font=("Segoe UI", 8, "bold"), anchor="w")
        self.canvas.create_line(w - 260, 52, w - 230, 52, fill="#4ade80", width=2)
        self.canvas.create_text(w - 225, 52, text=f"Line 2: {name2}", fill="#f8fafc", font=("Segoe UI", 8, "bold"), anchor="w")

        p1 = self.channel_1_points
        self.cur_val_var.set(f"{name1} (Cyan): {p1[-1]:.4g}")
        self.ch2_val_var.set(f"{name2} (Green): {self.channel_2_points[-1]:.4g}" if self.channel_2_points else "Ch2 (Green): N/A")
        self.min_val_var.set(f"Min: {min(p1):.4g}")
        self.max_val_var.set(f"Max: {max(p1):.4g}")
        self.avg_val_var.set(f"Avg: {sum(p1) / len(p1):.4g}")


class AutomationScriptRunnerView(ttk.Frame):
    """Runs a script with the shared :class:`ScriptRunner` and shows the real result of every step."""

    def __init__(
        self,
        parent: tk.Widget,
        catalog: CatalogManager,
        on_run: Callable[..., Optional["Future[Any]"]],
    ) -> None:
        """``on_run(script, spec, on_step, on_done)`` starts the run and returns its future (None if not connected)."""
        super().__init__(parent, padding=12)
        self.catalog = catalog
        self.on_run = on_run
        self.is_running = False
        self._future: Optional["Future[Any]"] = None

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(paned, padding=8)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Select Test Script Sequence:").pack(anchor="w")
        self.script_var = tk.StringVar()
        self.script_combo = ttk.Combobox(left_frame, textvariable=self.script_var)
        self.script_combo.pack(fill=tk.X, pady=(0, 8))

        controls = ttk.Frame(left_frame)
        controls.pack(fill=tk.X, pady=4)
        self.run_btn = ttk.Button(controls, text="▶ Run Script", command=self._run_script)
        self.run_btn.pack(side=tk.LEFT, padx=2)
        self.stop_btn = ttk.Button(controls, text="⏹ Stop", command=self._stop_script, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        self.steps_tree = ttk.Treeview(left_frame, columns=("step", "cmd", "delay", "result"), show="headings", height=8)
        for column, title, width in (("step", "Step", 45), ("cmd", "Command", 150), ("delay", "Delay (ms)", 75), ("result", "Result", 80)):
            self.steps_tree.heading(column, text=title)
            self.steps_tree.column(column, width=width)
        self.steps_tree.pack(fill=tk.BOTH, expand=True, pady=8)

        right_frame = ttk.LabelFrame(paned, text=" Execution Output Log ", padding=8)
        paned.add(right_frame, weight=2)

        self.log_text = tk.Text(right_frame, bg="#0f172a", fg="#f8fafc", font=("Consolas", 10), wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._populate_scripts()

    def _log(self, text: str) -> None:
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log_text.see(tk.END)

    def _populate_scripts(self) -> None:
        summary = self.catalog.catalog_summary()
        script_ids = [s.get("filename", "") for s in summary.get("scripts", [])]
        self.script_combo["values"] = script_ids
        if script_ids:
            self.script_var.set(script_ids[0])
            self._load_steps(script_ids[0])
        self.script_combo.bind("<<ComboboxSelected>>", lambda e: self._load_steps(self.script_var.get()))

    def _load_steps(self, script_id: str) -> None:
        for item in self.steps_tree.get_children():
            self.steps_tree.delete(item)
        script = self.catalog.get_script(script_id)
        if not script:
            return
        for idx, step in enumerate(script.steps, 1):
            label = step.command or step.name or ("delay" if step.delay_ms else "log")
            self.steps_tree.insert("", tk.END, iid=str(idx), values=(idx, label, step.delay_ms or "", ""))

    def _run_script(self) -> None:
        script = self.catalog.get_script(self.script_var.get())
        if script is None:
            self._log(f"Cannot load script '{self.script_var.get()}'.")
            return
        spec = self.catalog.resolve_script_protocol(script)
        if spec is None:
            self._log(f"Cannot run: protocol '{script.meta.protocol}' referenced by the script was not found.")
            return
        self._load_steps(self.script_var.get())
        future = self.on_run(script, spec, self._on_step, self._on_done)
        if future is None:
            self._log("Not connected. Connect a serial port or the virtual device first.")
            return
        self._future = future
        self.is_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self._log(f"Starting '{script.meta.name}' on the connected link...")

    def _on_step(self, result: Any) -> None:
        """Called on the Tk thread with a :class:`StepResult`."""
        iid = str(result.index)
        if self.steps_tree.exists(iid):
            self.steps_tree.set(iid, "result", result.status.value.upper())
        detail = f" - {result.message}" if result.message else ""
        self._log(f"Step {result.index} {result.name}: {result.status.value.upper()}{detail} ({result.duration_ms:.0f} ms)")
        for assertion in result.assertions:
            mark = "PASS" if assertion.passed else "FAIL"
            self._log(f"    {mark} {assertion.field} {assertion.op} {assertion.expected!r} (actual {assertion.actual!r})")

    def _on_done(self, result: Any, error: Optional[BaseException], cancelled: bool) -> None:
        """Called on the Tk thread when the run ends."""
        if cancelled:
            self._log("Script stopped.")
        elif error is not None:
            self._log(f"Script aborted: {type(error).__name__}: {error}")
        else:
            self._log(f"Script {'PASSED' if result.passed else 'FAILED'} (exit code {result.exit_code}).")
        self._finish()

    def _finish(self) -> None:
        self.is_running = False
        self._future = None
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def _stop_script(self) -> None:
        if self._future is not None:
            self._future.cancel()


class CommsStreamerView(ttk.Frame):
    """Raw Hex/ASCII Comms Streamer Console Tab with Dual Decoded Packet Field Breakdown."""

    def __init__(self, parent: tk.Widget, on_transmit: Callable[[str, bytes], None]) -> None:
        """``on_transmit(label, raw_bytes)`` sends raw bytes on the link and logs the traffic."""
        super().__init__(parent, padding=12)
        self.on_transmit = on_transmit
        self.is_recording = False

        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(toolbar, text="Display Mode:").pack(side=tk.LEFT, padx=4)
        self.mode_var = tk.StringVar(value="Dual (Raw Hex + Decoded Fields)")
        ttk.Combobox(
            toolbar,
            textvariable=self.mode_var,
            values=["Dual (Raw Hex + Decoded Fields)", "Hex + ASCII", "Hex Only", "ASCII Only", "Decoded Fields Only"],
            width=30,
        ).pack(side=tk.LEFT, padx=4)

        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Autoscroll", variable=self.autoscroll_var).pack(side=tk.LEFT, padx=8)

        self.rec_btn = ttk.Button(toolbar, text="🔴 Record Stream", command=self._toggle_recording)
        self.rec_btn.pack(side=tk.LEFT, padx=4)

        self.export_btn = ttk.Button(toolbar, text="💾 Export Log", command=self._export_log)
        self.export_btn.pack(side=tk.LEFT, padx=4)

        ttk.Button(toolbar, text="Clear Stream", command=self.clear).pack(side=tk.RIGHT, padx=4)

        # Serial monitor text view
        self.console = tk.Text(self, bg="#0b0f19", fg="#f8fafc", font=("Consolas", 10), wrap="word")
        self.console.pack(fill=tk.BOTH, expand=True)

        self.console.tag_config("TX", foreground="#38bdf8")
        self.console.tag_config("RX", foreground="#4ade80")
        self.console.tag_config("ERR", foreground="#f87171")
        self.console.tag_config("TIME", foreground="#64748b")
        self.console.tag_config("SYS", foreground="#a78bfa")
        self.console.tag_config("DECODED", foreground="#fbbf24")

        # Raw transmit bar
        tx_bar = ttk.Frame(self)
        tx_bar.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(tx_bar, text="Send Raw Hex/ASCII:").pack(side=tk.LEFT, padx=4)
        self.raw_input = ttk.Entry(tx_bar)
        self.raw_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.raw_input.bind("<Return>", lambda e: self._send_raw())

        ttk.Button(tx_bar, text="Send Packet", command=self._send_raw).pack(side=tk.RIGHT, padx=4)

    @staticmethod
    def _describe_bytes(data: bytes) -> str:
        """Plain facts about the bytes (length and ASCII/binary); no field layout is guessed."""
        if not data:
            return "Length: 0B"
        is_ascii = all(32 <= b <= 126 or b in (10, 13) for b in data)
        return f"Length: {len(data)}B | Type: {'ASCII' if is_ascii else 'Binary'}"

    def log(self, direction: str, data: bytes, label: str = "", decoded: str = "") -> None:
        """Append a TX/RX/ERR/SYS event. ``decoded`` is the codec's decoded fields, when there are any."""
        now = time.time()
        ts = f"[{time.strftime('%H:%M:%S', time.localtime(now))}.{int((now % 1) * 1000):03d}]"
        hex_str = " ".join(f"{b:02X}" for b in data)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)
        decoded_fields = self._describe_bytes(data) + (f" | {decoded}" if decoded else "")

        mode = self.mode_var.get()
        dir_tag = direction.upper() if direction.upper() in ("TX", "RX", "ERR", "SYS") else "RX"
        tag_str = f"[{dir_tag}] {label}: " if label else f"[{dir_tag}]: "

        self.console.insert(tk.END, f"{ts} ", "TIME")
        self.console.insert(tk.END, tag_str, dir_tag)

        if mode == "Hex Only":
            self.console.insert(tk.END, f"{hex_str}\n")
        elif mode == "ASCII Only":
            self.console.insert(tk.END, f"{ascii_str}\n")
        elif mode == "Decoded Fields Only":
            self.console.insert(tk.END, f"{decoded_fields}\n", "DECODED")
        elif mode == "Hex + ASCII":
            self.console.insert(tk.END, f"{hex_str} | '{ascii_str}'\n")
        else:
            self.console.insert(tk.END, f"{hex_str} | '{ascii_str}'\n")
            self.console.insert(tk.END, f"    └─ Decoded: {decoded_fields}\n", "DECODED")

        if self.autoscroll_var.get():
            self.console.see(tk.END)

    def _toggle_recording(self) -> None:
        """Toggle live stream recording session status."""
        self.is_recording = not self.is_recording
        if self.is_recording:
            self.rec_btn.config(text="⏹ Stop Recording")
            self.log("SYS", b"=== SESSION RECORDING STARTED ===", "Recorder")
        else:
            self.rec_btn.config(text="🔴 Record Stream")
            self.log("SYS", b"=== SESSION RECORDING STOPPED ===", "Recorder")

    def _export_log(self) -> None:
        """Export live serial stream console buffer to file on disk."""
        content = self.console.get("1.0", tk.END)
        if not content.strip():
            messagebox.showinfo("Export Stream Log", "Stream console buffer is empty.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log Files", "*.log"), ("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Export Serial Stream Log",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Export Stream Log", f"Saved stream log to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to save log file: {e}")

    def clear(self) -> None:
        self.console.delete("1.0", tk.END)

    def _send_raw(self) -> None:
        raw_text = self.raw_input.get().strip()
        if not raw_text:
            return

        try:
            cleaned = raw_text.replace(" ", "")
            raw_bytes = bytes.fromhex(cleaned)
        except ValueError:
            raw_bytes = raw_text.encode("utf-8")

        self.on_transmit("Raw Direct", raw_bytes)
        self.raw_input.delete(0, tk.END)
