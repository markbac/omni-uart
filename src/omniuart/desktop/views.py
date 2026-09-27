"""Tkinter Desktop View Components for OmniUART Native Desktop GUI Application."""

from __future__ import annotations

import math
import random
import struct
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from omniuart.core.catalog import CatalogManager
from omniuart.core.models import CommandSpec, ProtocolSpec


def build_frame_payload(spec: ProtocolSpec, cmd: CommandSpec, params: Dict[str, Any]) -> bytes:
    """Build raw frame byte payload for a command according to protocol framing spec."""
    payload_buf = bytearray()

    # Append opcode/discriminator if present
    disc_val = getattr(cmd, "discriminator", None)
    if disc_val is not None:
        payload_buf.append(int(disc_val) & 0xFF)

    # Encode parameters into payload
    for param in cmd.parameters:
        val = params.get(param.name, param.default if param.default is not None else 0)
        try:
            if param.type.value in ("uint8", "int8", "enum"):
                int_val = int(val)
                fmt = ">B" if param.endian == "big" else "<B"
                payload_buf.extend(struct.pack(fmt, int_val & 0xFF))
            elif param.type.value in ("uint16", "int16"):
                int_val = int(val)
                fmt = ">H" if param.endian == "big" else "<H"
                payload_buf.extend(struct.pack(fmt, int_val & 0xFFFF))
            elif param.type.value in ("uint32", "int32"):
                int_val = int(val)
                fmt = ">I" if param.endian == "big" else "<I"
                payload_buf.extend(struct.pack(fmt, int_val & 0xFFFFFFFF))
            elif param.type.value in ("float", "float32"):
                flt_val = float(val)
                fmt = ">f" if param.endian == "big" else "<f"
                payload_buf.extend(struct.pack(fmt, flt_val))
            elif param.type.value in ("double", "float64"):
                flt_val = float(val)
                fmt = ">d" if param.endian == "big" else "<d"
                payload_buf.extend(struct.pack(fmt, flt_val))
            elif param.type.value == "bool":
                bool_val = 1 if bool(val) else 0
                payload_buf.append(bool_val)
            else:
                str_val = str(val).encode("utf-8")
                payload_buf.extend(str_val)
        except Exception:
            payload_buf.extend(b"\x00")

    # Construct complete frame envelope
    frame = bytearray()
    framing = spec.framing

    if framing.type.value == "delimited":
        prefix = (framing.prefix or "").encode("utf-8")
        delimiter = (framing.delimiter or " ").encode("utf-8")
        suffix = (framing.suffix or "\r\n").encode("utf-8")

        frame.extend(prefix)
        frame.extend(str(cmd.id).encode("utf-8"))
        if payload_buf:
            frame.extend(delimiter)
            frame.extend(payload_buf)
        frame.extend(suffix)

    else:
        # Binary framing
        if framing.header:
            if isinstance(framing.header, list):
                frame.extend(bytes(framing.header))
            elif isinstance(framing.header, str):
                frame.extend(bytes.fromhex(framing.header.replace(" ", "")))

        # Command ID / Opcode
        if isinstance(cmd.id, int):
            cmd_id_spec = framing.command_id
            endian = cmd_id_spec.endian if cmd_id_spec else "little"
            if cmd_id_spec and cmd_id_spec.type == "uint16":
                fmt = ">H" if endian == "big" else "<H"
                frame.extend(struct.pack(fmt, cmd.id))
            else:
                frame.append(cmd.id & 0xFF)

        # Length field if required
        if framing.length:
            length_val = len(payload_buf)
            fmt = ">H" if framing.length.endian == "big" else "<H"
            frame.extend(struct.pack(fmt, length_val))

        frame.extend(payload_buf)

        # Integrity Checksum / CRC
        if framing.integrity:
            crc_sum = sum(frame) & 0xFFFF
            fmt = ">H" if framing.integrity.endian == "big" else "<H"
            frame.extend(struct.pack(fmt, crc_sum))

        # Footer
        if framing.footer:
            if isinstance(framing.footer, list):
                frame.extend(bytes(framing.footer))
            elif isinstance(framing.footer, str):
                frame.extend(bytes.fromhex(framing.footer.replace(" ", "")))

    return bytes(frame)


class ConnectionToolbar(ttk.Frame):
    """Header toolbar for physical serial connection configuration and status."""

    def __init__(self, parent: tk.Widget, on_connect_toggle: Callable[[Dict[str, Any]], None]) -> None:
        super().__init__(parent, padding=(10, 8, 10, 8))
        self.on_connect_toggle = on_connect_toggle
        self.is_connected = False

        # Physical serial settings widgets
        ttk.Label(self, text="Serial Port:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=4)
        self.port_var = tk.StringVar(value="COM1")
        self.port_combo = ttk.Combobox(
            self, textvariable=self.port_var, values=["COM1", "COM2", "COM3", "/dev/ttyUSB0", "/dev/ttyACM0"], width=12
        )
        self.port_combo.pack(side=tk.LEFT, padx=4)

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

    def _toggle_connection(self) -> None:
        self.is_connected = not self.is_connected
        if self.is_connected:
            self.connect_btn.config(text="🔌 Disconnect")
            self.status_label.config(
                text=f"● Connected ({self.port_var.get()} @ {self.baud_var.get()})", foreground="#16a34a"
            )
        else:
            self.connect_btn.config(text="⚡ Connect")
            self.status_label.config(text="● Disconnected", foreground="#dc2626")

        config = {
            "connected": self.is_connected,
            "port": self.port_var.get(),
            "baudrate": int(self.baud_var.get()),
            "databits": int(self.databits_var.get()),
            "parity": self.parity_var.get(),
            "stopbits": float(self.stopbits_var.get()),
            "rts": self.rts_var.get(),
            "dtr": self.dtr_var.get(),
        }
        self.on_connect_toggle(config)


class DashboardView(ttk.Frame):
    """Dashboard tab showing overview metrics, serial status, and loaded protocols."""

    def __init__(self, parent: tk.Widget, catalog: CatalogManager) -> None:
        super().__init__(parent, padding=16)
        self.catalog = catalog

        # Metrics cards frame
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill=tk.X, pady=10)

        summary = catalog.catalog_summary()
        protocols_count = summary.get("protocols_found", 0)
        scripts_count = summary.get("scripts_found", 0)

        self._create_card(cards_frame, "Loaded Protocols", str(protocols_count), "#2563eb", 0)
        self._create_card(cards_frame, "Automation Scripts", str(scripts_count), "#7c3aed", 1)
        self._create_card(cards_frame, "TX Bytes Sent", "0 B", "#059669", 2)
        self._create_card(cards_frame, "RX Bytes Received", "0 B", "#d97706", 3)

        # Overview section
        overview_frame = ttk.LabelFrame(self, text=" Loaded Protocol Schemas ", padding=12)
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
        """Populate protocol schema treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        summary = self.catalog.catalog_summary()
        for p in summary.get("protocols", []):
            self.tree.insert(
                "",
                tk.END,
                values=(
                    p.get("filename", ""),
                    p.get("name", ""),
                    p.get("version", ""),
                    "UART",
                    p.get("commands_count", 0),
                ),
            )


class CommandCatalogView(ttk.Frame):
    """Command catalog browser and dynamic parameter builder tab."""

    def __init__(self, parent: tk.Widget, catalog: CatalogManager, on_transmit: Callable[[str, bytes], None]) -> None:
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

        self.cmd_title_label = ttk.Label(right_frame, text="Select a command from the tree", font=("Segoe UI", 11, "bold"))
        self.cmd_title_label.pack(anchor="w", pady=(0, 4))

        self.cmd_desc_label = ttk.Label(right_frame, text="", wraplength=450, foreground="#64748b")
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

        summary = self.catalog.catalog_summary()
        for p in summary.get("protocols", []):
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
        disc_text = f" | Discriminator: 0x{int(disc_val):02X}" if disc_val is not None else ""
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
            raw_bytes = build_frame_payload(self.selected_proto, self.selected_cmd, param_dict)
            self.on_transmit(self.selected_cmd.name, raw_bytes)
        except Exception as e:
            messagebox.showerror("Transmission Error", f"Failed to build payload: {e}")


class TelemetryPlotterView(ttk.Frame):
    """Real-time Canvas Telemetry Line Chart Plotter."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, padding=12)
        self.data_points: List[float] = [50.0] * 50
        self.is_running = True

        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(toolbar, text="Real-Time Telemetry Line Chart Plotter", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        self.pause_btn = ttk.Button(toolbar, text="Pause Plotter", command=self._toggle_plotter)
        self.pause_btn.pack(side=tk.RIGHT, padx=4)
        ttk.Button(toolbar, text="Clear Data", command=self._clear_plotter).pack(side=tk.RIGHT, padx=4)

        # Plotter canvas
        self.canvas = tk.Canvas(self, bg="#0f172a", highlightthickness=1, highlightbackground="#334155")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._schedule_update()

    def _toggle_plotter(self) -> None:
        self.is_running = not self.is_running
        self.pause_btn.config(text="Resume Plotter" if not self.is_running else "Pause Plotter")

    def _clear_plotter(self) -> None:
        self.data_points = [50.0] * 50
        self._draw_chart()

    def push_value(self, val: float) -> None:
        """Push real telemetry value into chart dataset."""
        self.data_points.append(val)
        if len(self.data_points) > 100:
            self.data_points.pop(0)
        self._draw_chart()

    def _schedule_update(self) -> None:
        if self.is_running:
            # Simulate real-time signal variation
            last = self.data_points[-1]
            new_val = max(10.0, min(90.0, last + random.uniform(-4.0, 4.0)))
            self.push_value(new_val)
        self.after(200, self._schedule_update)

    def _draw_chart(self) -> None:
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            return

        # Draw grid lines
        for y in range(0, h, 40):
            self.canvas.create_line(0, y, w, y, fill="#1e293b", dash=(2, 4))
        for x in range(0, w, 50):
            self.canvas.create_line(x, 0, x, h, fill="#1e293b", dash=(2, 4))

        # Plot waveform
        if not self.data_points:
            return

        step = w / max(1, len(self.data_points) - 1)
        coords = []
        for i, val in enumerate(self.data_points):
            x = i * step
            y = h - (val / 100.0 * (h - 20) + 10)
            coords.extend([x, y])

        if len(coords) >= 4:
            self.canvas.create_line(*coords, fill="#38bdf8", width=2, smooth=True)


class AutomationScriptRunnerView(ttk.Frame):
    """Interactive Automation Sequence Runner Tab."""

    def __init__(self, parent: tk.Widget, catalog: CatalogManager, on_transmit: Callable[[str, bytes], None]) -> None:
        super().__init__(parent, padding=12)
        self.catalog = catalog
        self.on_transmit = on_transmit
        self.is_running = False

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

        self.steps_tree = ttk.Treeview(left_frame, columns=("step", "cmd", "delay"), show="headings", height=8)
        self.steps_tree.heading("step", text="Step")
        self.steps_tree.heading("cmd", text="Command")
        self.steps_tree.heading("delay", text="Delay (ms)")
        self.steps_tree.column("step", width=50)
        self.steps_tree.column("cmd", width=160)
        self.steps_tree.column("delay", width=80)
        self.steps_tree.pack(fill=tk.BOTH, expand=True, pady=8)

        right_frame = ttk.LabelFrame(paned, text=" Execution Output Log ", padding=8)
        paned.add(right_frame, weight=2)

        self.log_text = tk.Text(right_frame, bg="#0f172a", fg="#f8fafc", font=("Consolas", 10), wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._populate_scripts()

    def _populate_scripts(self) -> None:
        summary = self.catalog.catalog_summary()
        scripts = summary.get("scripts", [])
        script_ids = [s.get("filename", "") for s in scripts]
        self.script_combo["values"] = script_ids
        if script_ids:
            self.script_var.set(script_ids[0])
            self._load_steps(script_ids[0])
        self.script_combo.bind("<<ComboboxSelected>>", lambda e: self._load_steps(self.script_var.get()))

    def _load_steps(self, script_id: str) -> None:
        for item in self.steps_tree.get_children():
            self.steps_tree.delete(item)

        script = self.catalog.get_script(script_id)
        if not script or not hasattr(script, "steps"):
            return

        for idx, step in enumerate(script.steps, 1):
            cmd_name = getattr(step, "command", getattr(step, "name", str(step)))
            delay = getattr(step, "delay_ms", 100)
            self.steps_tree.insert("", tk.END, values=(idx, cmd_name, delay))

    def _run_script(self) -> None:
        self.is_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] Starting script execution...\n")
        self.log_text.see(tk.END)
        self._execute_step(0)

    def _execute_step(self, step_idx: int) -> None:
        children = self.steps_tree.get_children()
        if not self.is_running or step_idx >= len(children):
            self._stop_script()
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] Script execution completed successfully.\n")
            self.log_text.see(tk.END)
            return

        item = self.steps_tree.item(children[step_idx])
        vals = item.get("values", [])
        cmd_name, delay = vals[1], int(vals[2])

        self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] Step {step_idx + 1}: Executing {cmd_name}...\n")
        self.log_text.see(tk.END)

        # Trigger mock payload
        self.on_transmit(str(cmd_name), b"\xAA\xBB\xCC")

        self.after(delay, lambda: self._execute_step(step_idx + 1))

    def _stop_script(self) -> None:
        self.is_running = False
        self.run_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)


class CommsStreamerView(ttk.Frame):
    """Raw Hex/ASCII Comms Streamer Console Tab."""

    def __init__(self, parent: tk.Widget, on_transmit: Callable[[str, bytes], None]) -> None:
        super().__init__(parent, padding=12)
        self.on_transmit = on_transmit

        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(toolbar, text="Display Mode:").pack(side=tk.LEFT, padx=4)
        self.mode_var = tk.StringVar(value="Hex + ASCII")
        ttk.Combobox(toolbar, textvariable=self.mode_var, values=["Hex + ASCII", "Hex Only", "ASCII Only"], width=12).pack(
            side=tk.LEFT, padx=4
        )

        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar, text="Autoscroll", variable=self.autoscroll_var).pack(side=tk.LEFT, padx=8)

        ttk.Button(toolbar, text="Clear Stream", command=self.clear).pack(side=tk.RIGHT, padx=4)

        # Serial monitor text view
        self.console = tk.Text(self, bg="#0b0f19", fg="#f8fafc", font=("Consolas", 10), wrap="word")
        self.console.pack(fill=tk.BOTH, expand=True)

        self.console.tag_config("TX", foreground="#38bdf8")
        self.console.tag_config("RX", foreground="#4ade80")
        self.console.tag_config("ERR", foreground="#f87171")
        self.console.tag_config("TIME", foreground="#64748b")

        # Raw transmit bar
        tx_bar = ttk.Frame(self)
        tx_bar.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(tx_bar, text="Send Raw Hex/ASCII:").pack(side=tk.LEFT, padx=4)
        self.raw_input = ttk.Entry(tx_bar)
        self.raw_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.raw_input.bind("<Return>", lambda e: self._send_raw())

        ttk.Button(tx_bar, text="Send Packet", command=self._send_raw).pack(side=tk.RIGHT, padx=4)

    def log(self, direction: str, data: bytes, label: str = "") -> None:
        """Append RX/TX packet event to console."""
        ts = time.strftime("[%H:%M:%S.%3d]")
        hex_str = " ".join(f"{b:02X}" for b in data)
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in data)

        mode = self.mode_var.get()
        if mode == "Hex Only":
            payload = hex_str
        elif mode == "ASCII Only":
            payload = ascii_str
        else:
            payload = f"{hex_str} | '{ascii_str}'"

        dir_tag = "TX" if direction.upper() == "TX" else "RX"
        tag_str = f"[{dir_tag}] {label}: " if label else f"[{dir_tag}]: "

        self.console.insert(tk.END, f"{ts} ", "TIME")
        self.console.insert(tk.END, tag_str, dir_tag)
        self.console.insert(tk.END, f"{payload}\n")

        if self.autoscroll_var.get():
            self.console.see(tk.END)

    def clear(self) -> None:
        self.console.delete("1.0", tk.END)

    def _send_raw(self) -> None:
        raw_text = self.raw_input.get().strip()
        if not raw_text:
            return

        try:
            # Parse hex or ASCII
            cleaned = raw_text.replace(" ", "")
            raw_bytes = bytes.fromhex(cleaned)
        except ValueError:
            raw_bytes = raw_text.encode("utf-8")

        self.log("TX", raw_bytes, "Raw Direct")
        self.on_transmit("Raw Direct", raw_bytes)
        self.raw_input.delete(0, tk.END)
