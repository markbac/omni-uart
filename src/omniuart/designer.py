"""Visual and Programmatic Device UI Designer for OmniUART (#241).

Allows users to arrange sections and widgets, bind protocol fields, configure labels
and safety rules, preview against device models, and export declarative DeviceUISpec definitions.
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path
from typing import Any, List, Optional

from omniuart.core.device_ui import (
    DeviceUICompatibilityReport,
    DeviceUISpec,
    DeviceUIStore,
    GroupSpec,
    PanelSpec,
    SafetyRuleSpec,
    WidgetSpec,
    check_protocol_compatibility,
    export_device_ui,
    infer_device_ui_from_spec,
    infer_widget_for_field,
)
from omniuart.core.models import ProtocolSpec
from omniuart.dashboard_generator import generate_device_dashboard_html

logger = logging.getLogger(__name__)


class DeviceUIDesigner:
    """Visual and programmatic Device UI Designer for building and editing DeviceUISpec definitions (#241)."""

    def __init__(
        self,
        protocol: ProtocolSpec,
        ui_spec: Optional[DeviceUISpec] = None,
        store: Optional[DeviceUIStore] = None,
    ) -> None:
        self.protocol = protocol
        self.ui_spec = ui_spec.model_copy(deep=True) if ui_spec else infer_device_ui_from_spec(protocol)
        self.store = store or DeviceUIStore()

    def add_panel(self, name: str, title: str) -> PanelSpec:
        """Add a new workspace panel to the UI specification (#241)."""
        for p in self.ui_spec.panels:
            if p.name == name:
                return p
        panel = PanelSpec(name=name, title=title, groups=[])
        self.ui_spec.panels.append(panel)
        return panel

    def remove_panel(self, name: str) -> bool:
        """Remove a panel by name (#241)."""
        initial_len = len(self.ui_spec.panels)
        self.ui_spec.panels = [p for p in self.ui_spec.panels if p.name != name]
        return len(self.ui_spec.panels) < initial_len

    def reorder_panels(self, panel_names: List[str]) -> None:
        """Reorder panels according to given list of names (#241)."""
        panel_map = {p.name: p for p in self.ui_spec.panels}
        ordered = [panel_map[name] for name in panel_names if name in panel_map]
        for p in self.ui_spec.panels:
            if p not in ordered:
                ordered.append(p)
        self.ui_spec.panels = ordered

    def add_group(
        self,
        panel_name: str,
        name: str,
        title: str,
        layout: str = "grid",
    ) -> GroupSpec:
        """Add a widget group to a panel (#241)."""
        panel = self._get_panel(panel_name)
        for g in panel.groups:
            if g.name == name:
                return g
        group = GroupSpec(name=name, title=title, layout=layout, widgets=[])
        panel.groups.append(group)
        return group

    def remove_group(self, panel_name: str, group_name: str) -> bool:
        """Remove a widget group from a panel (#241)."""
        panel = self._get_panel(panel_name)
        initial_len = len(panel.groups)
        panel.groups = [g for g in panel.groups if g.name != group_name]
        return len(panel.groups) < initial_len

    def reorder_groups(self, panel_name: str, group_names: List[str]) -> None:
        """Reorder groups inside a panel (#241)."""
        panel = self._get_panel(panel_name)
        group_map = {g.name: g for g in panel.groups}
        ordered = [group_map[name] for name in group_names if name in group_map]
        for g in panel.groups:
            if g not in ordered:
                ordered.append(g)
        panel.groups = ordered

    def add_widget(
        self,
        panel_name: str,
        group_name: str,
        widget: WidgetSpec,
    ) -> None:
        """Add a widget to a specific panel and group (#241)."""
        group = self._get_group(panel_name, group_name)
        group.widgets.append(widget)

    def remove_widget(
        self,
        panel_name: str,
        group_name: str,
        field_ref: str,
    ) -> bool:
        """Remove a widget from a specific group by field_ref (#241)."""
        group = self._get_group(panel_name, group_name)
        initial_len = len(group.widgets)
        group.widgets = [w for w in group.widgets if w.field_ref != field_ref]
        return len(group.widgets) < initial_len

    def reorder_widgets(
        self,
        panel_name: str,
        group_name: str,
        field_refs: List[str],
    ) -> None:
        """Reorder widgets inside a group by field references (#241)."""
        group = self._get_group(panel_name, group_name)
        widget_map = {w.field_ref: w for w in group.widgets if w.field_ref}
        ordered = [widget_map[ref] for ref in field_refs if ref in widget_map]
        for w in group.widgets:
            if w not in ordered:
                ordered.append(w)
        group.widgets = ordered

    def update_widget(self, field_ref: str, **kwargs: Any) -> bool:
        """Update properties of a widget identified by field_ref (#241)."""
        found = False
        for panel in self.ui_spec.panels:
            for group in panel.groups:
                for widget in group.widgets:
                    if widget.field_ref == field_ref:
                        for k, v in kwargs.items():
                            if hasattr(widget, k):
                                setattr(widget, k, v)
                                found = True
        return found

    def bind_field(
        self,
        field_name: str,
        is_writable: bool = True,
        panel_name: str = "main",
        group_name: Optional[str] = None,
    ) -> WidgetSpec:
        """Bind a protocol parameter or telemetry field to an automatically inferred widget (#241)."""
        # Search command parameters
        target_field = None
        cmd_safety = None
        for cmd in self.protocol.commands:
            for p in cmd.parameters:
                if p.name == field_name:
                    target_field = p
                    cmd_safety = cmd.safety
                    break
            if target_field:
                break

        # Search telemetry
        if not target_field:
            for tel in self.protocol.telemetry:
                for f in tel.fields:
                    if f.name == field_name:
                        target_field = f
                        is_writable = False
                        break
                if target_field:
                    break

        if not target_field:
            # Check if field_name is a command name
            for cmd in self.protocol.commands:
                if cmd.name == field_name:
                    widget = WidgetSpec(
                        widget_type="button",
                        field_ref=cmd.name,
                        label=f"Execute {cmd.name.replace('_', ' ').title()}",
                    )
                    target_group = group_name or ("controls" if is_writable else "telemetry")
                    self.add_widget(panel_name, target_group, widget)
                    return widget

            raise ValueError(f"Field or command '{field_name}' not found in protocol '{self.protocol.metadata.name}'")

        widget = infer_widget_for_field(target_field, is_writable=is_writable, safety=cmd_safety)
        target_group = group_name or ("controls" if is_writable else "telemetry")
        self.add_widget(panel_name, target_group, widget)
        return widget

    def add_safety_rule(
        self,
        command: str,
        require_confirmation: bool = True,
        danger_zone: bool = True,
        warning_message: Optional[str] = None,
    ) -> None:
        """Add or update a safety rule for a command (#241)."""
        for r in self.ui_spec.safety_rules:
            if r.command == command:
                r.require_confirmation = require_confirmation
                r.danger_zone = danger_zone
                r.warning_message = warning_message
                return
        rule = SafetyRuleSpec(
            command=command,
            require_confirmation=require_confirmation,
            danger_zone=danger_zone,
            warning_message=warning_message,
        )
        self.ui_spec.safety_rules.append(rule)

    def remove_safety_rule(self, command: str) -> bool:
        """Remove a safety rule for a command (#241)."""
        initial_len = len(self.ui_spec.safety_rules)
        self.ui_spec.safety_rules = [r for r in self.ui_spec.safety_rules if r.command != command]
        return len(self.ui_spec.safety_rules) < initial_len

    def validate(self) -> DeviceUICompatibilityReport:
        """Validate current UI specification against underlying protocol (#241, #242)."""
        return check_protocol_compatibility(self.ui_spec, self.protocol)

    def export_yaml(self) -> str:
        """Export current UI specification as YAML (#241, #242)."""
        return export_device_ui(self.ui_spec, format="yaml")

    def export_json(self) -> str:
        """Export current UI specification as JSON (#241, #242)."""
        return export_device_ui(self.ui_spec, format="json")

    def save(self, filename: Optional[str] = None, format: str = "yaml") -> Path:
        """Persist current UI specification to store repository (#241, #242)."""
        return self.store.save(self.ui_spec, filename=filename, format=format)

    def generate_preview_html(
        self,
        connection_status: str = "CONNECTED",
        is_connected: bool = True,
    ) -> str:
        """Generate live console preview HTML driven by current UI specification (#241)."""
        return generate_device_dashboard_html(
            self.protocol,
            self.ui_spec,
            connection_status=connection_status,
            is_connected=is_connected,
        )

    def generate_editor_html(self) -> str:
        """Generate interactive visual Device UI Designer editor HTML (#241)."""
        return generate_designer_html(self.protocol, self.ui_spec)

    def _get_panel(self, name: str) -> PanelSpec:
        for p in self.ui_spec.panels:
            if p.name == name:
                return p
        return self.add_panel(name, name.replace("_", " ").title())

    def _get_group(self, panel_name: str, group_name: str) -> GroupSpec:
        panel = self._get_panel(panel_name)
        for g in panel.groups:
            if g.name == group_name:
                return g
        return self.add_group(panel_name, group_name, group_name.replace("_", " ").title())


# Client-side editor. Kept out of the f-string below so its braces need no doubling.
_DESIGNER_SCRIPT = r"""
(function() {
  'use strict';
  const state = JSON.parse(document.getElementById('initial-data').textContent);
  const spec = state.ui_spec;
  spec.panels = spec.panels || [];
  spec.safety_rules = spec.safety_rules || [];
  const COMMAND_WIDGETS = ['button', 'file_transfer', 'firmware_update'];
  let selected = null;      // {p, g, w} indices of the selected widget
  let targetGroup = null;   // {p, g} indices that new bindings go to
  let dragFrom = null;

  function el(tag, attrs, text) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'class') node.className = v; else node.setAttribute(k, v);
    }
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function title(name) {
    return String(name).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function findCommand(name) {
    return (state.protocol.commands || []).find(c => c.name === name) || null;
  }

  function findField(name) {
    for (const c of state.protocol.commands || []) {
      for (const p of c.parameters || []) if (p.name === name) return {field: p, writable: true, command: c};
    }
    for (const t of state.protocol.telemetry || []) {
      for (const f of t.fields || []) if (f.name === name) return {field: f, writable: false, command: null};
    }
    return null;
  }

  // Mirrors infer_widget_for_field in core/device_ui.py.
  function inferWidget(field, writable, kind) {
    const type = String(field.type || '').toLowerCase();
    const numeric = /^(u?int(8|16|32|64)|float(32|64)?|double)$/.test(type);
    const w = {widget_type: 'text', field_ref: field.name, label: title(field.name), unit: field.unit || null,
               min: field.min ?? null, max: field.max ?? null, step: null, options: null};
    if (!writable) {
      w.widget_type = kind || (type === 'bool' || type === 'boolean' ? 'badge' : (numeric ? 'gauge' : 'text'));
      return w;
    }
    if (field.options || type === 'enum') { w.widget_type = 'dropdown'; w.options = field.options || null; }
    else if (type === 'bool' || type === 'boolean') w.widget_type = 'switch';
    else if (field.min !== null && field.min !== undefined && field.max !== null && field.max !== undefined) {
      const isFloat = type.startsWith('float');
      if (field.max - field.min <= 100 || isFloat) { w.widget_type = 'slider'; w.step = isFloat ? 0.1 : 1; }
      else w.widget_type = 'number_input';
    } else w.widget_type = numeric ? 'number_input' : 'text_input';
    return w;
  }

  function ensureTargetGroup(preferred) {
    if (targetGroup && spec.panels[targetGroup.p] && spec.panels[targetGroup.p].groups[targetGroup.g]) return targetGroup;
    if (!spec.panels.length) spec.panels.push({name: 'main', title: 'Main Workspace', groups: []});
    for (let p = 0; p < spec.panels.length; p++) {
      const g = spec.panels[p].groups.findIndex(gr => gr.name === preferred);
      if (g >= 0) return {p, g};
    }
    const panel = spec.panels[0];
    if (!panel.groups.length) panel.groups.push({name: preferred, title: title(preferred), layout: 'grid', widgets: []});
    return {p: 0, g: 0};
  }

  function bind(name, kind) {
    let widget;
    const cmd = kind === 'button' ? findCommand(name) : null;
    if (cmd) {
      widget = {widget_type: 'button', field_ref: cmd.name, label: 'Execute ' + title(cmd.name)};
    } else {
      const found = findField(name);
      if (!found) { showModal('Bind failed', 'Field or command "' + name + '" is not in the protocol.'); return; }
      widget = inferWidget(found.field, found.writable, kind === 'control' ? null : kind);
    }
    const t = ensureTargetGroup(cmd || kind === 'control' ? 'controls' : 'telemetry');
    spec.panels[t.p].groups[t.g].widgets.push(widget);
    selected = {p: t.p, g: t.g, w: spec.panels[t.p].groups[t.g].widgets.length - 1};
    render();
  }

  function safetyRule(command) {
    return spec.safety_rules.find(r => r.command === command) || null;
  }

  function render() {
    const canvas = document.getElementById('canvas-area');
    canvas.replaceChildren();
    spec.panels.forEach((panel, pi) => {
      const pCard = el('div', {class: 'designer-panel-card', 'data-panel': panel.name});
      const pHead = el('div', {class: 'panel-header'});
      pHead.append(el('h3', {}, panel.title));
      const addGroup = el('button', {type: 'button', class: 'btn-xs'}, '+ Group');
      addGroup.addEventListener('click', () => {
        const name = prompt('New group name (identifier)', 'group_' + (panel.groups.length + 1));
        if (!name) return;
        panel.groups.push({name, title: title(name), layout: 'grid', widgets: []});
        targetGroup = {p: pi, g: panel.groups.length - 1};
        render();
      });
      pHead.append(addGroup);
      pCard.append(pHead);
      panel.groups.forEach((group, gi) => {
        const isTarget = targetGroup && targetGroup.p === pi && targetGroup.g === gi;
        const gCard = el('div', {class: 'designer-group-card' + (isTarget ? ' target' : ''), 'data-group': group.name});
        const gHead = el('div', {class: 'group-header'});
        const h4 = el('h4', {}, group.title + ' ');
        h4.append(el('span', {class: 'dim-label'}, '(' + group.name + ')'));
        gHead.append(h4);
        const ctl = el('div', {class: 'group-controls'});
        const tgt = el('button', {type: 'button', class: 'btn-xs btn-add-widget'}, isTarget ? 'Adding here' : '+ Add Widget');
        tgt.title = 'New bindings from the left sidebar are added to this group';
        tgt.addEventListener('click', () => { targetGroup = {p: pi, g: gi}; render(); });
        const del = el('button', {type: 'button', class: 'btn-icon', title: 'Delete group'}, '×');
        del.addEventListener('click', () => {
          if (group.widgets.length && !confirm('Delete group "' + group.title + '" and its widgets?')) return;
          panel.groups.splice(gi, 1); targetGroup = null; selected = null; render();
        });
        ctl.append(tgt, del);
        gHead.append(ctl);
        gCard.append(gHead);
        const wc = el('div', {class: 'widgets-container'});
        wc.addEventListener('dragover', e => { e.preventDefault(); wc.classList.add('drop'); });
        wc.addEventListener('dragleave', () => wc.classList.remove('drop'));
        wc.addEventListener('drop', e => {
          e.preventDefault(); wc.classList.remove('drop');
          if (!dragFrom) return;
          const [w] = spec.panels[dragFrom.p].groups[dragFrom.g].widgets.splice(dragFrom.w, 1);
          group.widgets.push(w);
          selected = {p: pi, g: gi, w: group.widgets.length - 1};
          dragFrom = null; render();
        });
        group.widgets.forEach((w, wi) => wc.append(widgetCard(w, pi, gi, wi)));
        gCard.append(wc);
        pCard.append(gCard);
      });
      canvas.append(pCard);
    });
    renderInspector();
  }

  function widgetCard(w, pi, gi, wi) {
    const isSel = selected && selected.p === pi && selected.g === gi && selected.w === wi;
    const card = el('div', {class: 'designer-widget-card' + (isSel ? ' selected' : ''), 'data-ref': w.field_ref || '',
                            'data-type': w.widget_type, draggable: 'true'});
    card.addEventListener('dragstart', () => { dragFrom = {p: pi, g: gi, w: wi}; });
    card.addEventListener('click', () => { selected = {p: pi, g: gi, w: wi}; render(); });
    const head = el('div', {class: 'widget-card-header'});
    head.append(el('span', {class: 'widget-type-badge'}, String(w.widget_type).toUpperCase()));
    head.append(el('span', {class: 'widget-label'}, w.label + (w.unit ? ' [' + w.unit + ']' : '')));
    const group = spec.panels[pi].groups[gi].widgets;
    const up = el('button', {type: 'button', class: 'btn-icon', title: 'Move up'}, '↑');
    up.addEventListener('click', e => { e.stopPropagation(); if (wi > 0) { [group[wi - 1], group[wi]] = [group[wi], group[wi - 1]]; selected = {p: pi, g: gi, w: wi - 1}; render(); } });
    const down = el('button', {type: 'button', class: 'btn-icon', title: 'Move down'}, '↓');
    down.addEventListener('click', e => { e.stopPropagation(); if (wi < group.length - 1) { [group[wi + 1], group[wi]] = [group[wi], group[wi + 1]]; selected = {p: pi, g: gi, w: wi + 1}; render(); } });
    const del = el('button', {type: 'button', class: 'btn-icon btn-del-widget', title: 'Delete widget'}, '×');
    del.addEventListener('click', e => { e.stopPropagation(); group.splice(wi, 1); selected = null; render(); });
    head.append(up, down, del);
    card.append(head);
    const ref = el('div', {class: 'widget-card-ref'}, 'field: ');
    ref.append(el('code', {}, w.field_ref || ''));
    card.append(ref);
    if (COMMAND_WIDGETS.includes(w.widget_type) && safetyRule(w.field_ref)) {
      card.append(el('div', {class: 'widget-card-ref safety'}, 'confirmation required'));
    }
    return card;
  }

  function current() {
    if (!selected) return null;
    const g = spec.panels[selected.p] && spec.panels[selected.p].groups[selected.g];
    return g ? g.widgets[selected.w] || null : null;
  }

  function renderInspector() {
    const w = current();
    document.getElementById('inspector-placeholder').style.display = w ? 'none' : 'block';
    document.getElementById('inspector-form').style.display = w ? 'block' : 'none';
    if (!w) return;
    const num = v => (v === undefined || v === null ? '' : v);
    document.getElementById('prop-ref').value = w.field_ref || '';
    document.getElementById('prop-label').value = w.label || '';
    document.getElementById('prop-type').value = w.widget_type || 'text';
    document.getElementById('prop-unit').value = w.unit || '';
    document.getElementById('prop-min').value = num(w.min);
    document.getElementById('prop-max').value = num(w.max);
    document.getElementById('prop-step').value = num(w.step);
    const isCommand = COMMAND_WIDGETS.includes(w.widget_type);
    document.getElementById('safety-section').style.display = isCommand ? 'block' : 'none';
    if (isCommand) {
      const rule = safetyRule(w.field_ref);
      const cmd = findCommand(w.field_ref);
      document.getElementById('prop-safety-level').textContent = cmd ? 'Protocol safety: ' + cmd.safety : 'Command not in protocol';
      document.getElementById('prop-confirm').checked = !!(rule && rule.require_confirmation);
      document.getElementById('prop-danger').checked = !!(rule && rule.danger_zone);
      document.getElementById('prop-warning').value = (rule && rule.warning_message) || '';
    }
  }

  document.getElementById('btn-apply-props').addEventListener('click', () => {
    const w = current();
    if (!w) return;
    const numOrNull = id => { const v = document.getElementById(id).value; return v === '' ? null : parseFloat(v); };
    w.label = document.getElementById('prop-label').value;
    w.widget_type = document.getElementById('prop-type').value;
    w.unit = document.getElementById('prop-unit').value || null;
    w.min = numOrNull('prop-min'); w.max = numOrNull('prop-max'); w.step = numOrNull('prop-step');
    if (COMMAND_WIDGETS.includes(w.widget_type) && w.field_ref) {
      const confirmOn = document.getElementById('prop-confirm').checked;
      const danger = document.getElementById('prop-danger').checked;
      const warning = document.getElementById('prop-warning').value || null;
      spec.safety_rules = spec.safety_rules.filter(r => r.command !== w.field_ref);
      if (confirmOn || danger || warning) {
        spec.safety_rules.push({command: w.field_ref, require_confirmation: confirmOn, danger_zone: danger, warning_message: warning});
      }
    }
    render();
  });

  document.querySelectorAll('.btn-bind').forEach(btn => {
    btn.addEventListener('click', () => bind(btn.getAttribute('data-bind-field'), btn.getAttribute('data-kind')));
  });

  document.getElementById('btn-add-panel').addEventListener('click', () => {
    const name = prompt('New panel name (identifier)', 'panel_' + (spec.panels.length + 1));
    if (!name) return;
    spec.panels.push({name, title: title(name), groups: []});
    render();
  });

  const modal = document.getElementById('modal-dialog');
  function showModal(heading, text) {
    document.getElementById('modal-title').textContent = heading;
    document.getElementById('modal-code').textContent = text;
    modal.style.display = 'flex';
  }
  document.getElementById('btn-close-modal').addEventListener('click', () => { modal.style.display = 'none'; });

  async function post(url, body) {
    const res = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) { /* not JSON */ }
      throw new Error(res.status + ': ' + detail);
    }
    return res;
  }
  function serverError(action, err) {
    showModal(action + ' failed', String(err.message || err) +
      '\n\nThis needs the OmniUART web server (omniuart designer <protocol>).');
  }

  document.getElementById('btn-export-json').addEventListener('click', () => {
    showModal('Device UI definition (JSON)', JSON.stringify(spec, null, 2));
  });
  document.getElementById('btn-export-yaml').addEventListener('click', async () => {
    try {
      const res = await post('/api/designer/export', {ui_spec: spec, format: 'yaml'});
      showModal('Device UI definition (YAML)', await res.text());
    } catch (err) { serverError('YAML export', err); }
  });
  document.getElementById('btn-save').addEventListener('click', async () => {
    try {
      const res = await post('/api/designer/save', {ui_spec: spec, format: 'yaml'});
      const out = await res.json();
      spec.revision = out.revision;
      showModal('Saved', 'Saved revision ' + out.revision + ' to ' + out.path);
    } catch (err) { serverError('Save', err); }
  });
  document.getElementById('btn-validate').addEventListener('click', async () => {
    try {
      const res = await post('/api/designer/validate', {protocol: state.protocol.metadata.name, ui_spec: spec});
      const report = await res.json();
      showModal(report.is_compatible ? 'Compatibility check: OK' : 'Compatibility issues found', JSON.stringify(report, null, 2));
    } catch (err) { serverError('Validation', err); }
  });
  document.getElementById('btn-preview').addEventListener('click', async () => {
    const win = window.open('', '_blank');
    try {
      const res = await post('/api/designer/preview', {protocol: state.protocol.metadata.name, ui_spec: spec});
      const url = URL.createObjectURL(new Blob([await res.text()], {type: 'text/html'}));
      if (win) win.location = url; else window.location = url;
    } catch (err) { if (win) win.close(); serverError('Preview', err); }
  });

  render();
})();
"""


def generate_designer_html(
    protocol: ProtocolSpec,
    ui_spec: Optional[DeviceUISpec] = None,
) -> str:
    """Generate standalone, interactive visual Device UI Designer editor HTML page (#241).

    All protocol metadata, command names, labels, and descriptions are strictly HTML-escaped (#316).
    """
    if ui_spec is None:
        ui_spec = infer_device_ui_from_spec(protocol)

    safe_title = html.escape(str(ui_spec.identity.name or protocol.metadata.name))
    safe_proto = html.escape(str(protocol.metadata.name))
    safe_version = html.escape(str(protocol.metadata.version or "1.0.0"))
    safe_vendor = html.escape(str(ui_spec.identity.vendor or protocol.metadata.author or "OmniUART"))

    # Initial JSON data for client-side interactivity
    initial_data = {
        "protocol": protocol.model_dump(mode="json"),
        "ui_spec": ui_spec.model_dump(mode="json"),
    }
    # Script element content is raw text (entities are not decoded), so escape only what could close the element.
    json_blob = json.dumps(initial_data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    # Build list of available protocol items
    commands_html = []
    for cmd in protocol.commands:
        cmd_name = html.escape(cmd.name)
        cmd_safety = cmd.safety.value if hasattr(cmd.safety, "value") else str(cmd.safety)
        params_info = f"{len(cmd.parameters)} params" if cmd.parameters else "no params"
        param_buttons = "".join(
            f'    <button type="button" class="btn-xs btn-bind" data-bind-field="{html.escape(p.name)}" data-kind="control">+ {html.escape(p.name)}</button>'
            for p in cmd.parameters
        )
        commands_html.append(
            f'<div class="protocol-item" data-type="command" data-name="{cmd_name}">'
            f'  <div class="item-header"><strong>{cmd_name}</strong> <span class="badge badge-{cmd_safety}">{cmd_safety}</span></div>'
            f'  <div class="item-meta">{params_info}</div>'
            f'  <div class="item-actions">'
            f'    <button type="button" class="btn-xs btn-bind" data-bind-field="{cmd_name}" data-kind="button">+ Button</button>'
            f'{param_buttons}'
            f'  </div>'
            f'</div>'
        )

    telemetry_html = []
    for tel in protocol.telemetry:
        for f in tel.fields:
            f_name = html.escape(f.name)
            f_type = html.escape(str(f.type.value if hasattr(f.type, "value") else f.type))
            f_unit = f" ({html.escape(f.unit)})" if f.unit else ""
            telemetry_html.append(
                f'<div class="protocol-item" data-type="telemetry" data-name="{f_name}">'
                f'  <div class="item-header"><strong>{f_name}</strong> <span class="badge badge-info">{f_type}{f_unit}</span></div>'
                f'  <div class="item-actions">'
                f'    <button type="button" class="btn-xs btn-bind" data-bind-field="{f_name}" data-kind="gauge">+ Gauge</button>'
                f'    <button type="button" class="btn-xs btn-bind" data-bind-field="{f_name}" data-kind="badge">+ Badge</button>'
                f'  </div>'
                f'</div>'
            )

    # Initial rendered layout canvas
    panels_canvas_html = []
    for panel in ui_spec.panels:
        p_name = html.escape(panel.name)
        p_title = html.escape(panel.title)
        groups_html = []
        for group in panel.groups:
            g_name = html.escape(group.name)
            g_title = html.escape(group.title)
            widgets_html = []
            for w in group.widgets:
                w_type = html.escape(w.widget_type)
                w_ref = html.escape(w.field_ref or "")
                w_label = html.escape(w.label)
                w_unit = f" [{html.escape(w.unit)}]" if w.unit else ""
                widgets_html.append(
                    f'<div class="designer-widget-card" data-ref="{w_ref}" data-type="{w_type}">'
                    f'  <div class="widget-card-header">'
                    f'    <span class="widget-type-badge">{w_type.upper()}</span>'
                    f'    <span class="widget-label">{w_label}{w_unit}</span>'
                    f'    <button type="button" class="btn-icon btn-del-widget" title="Delete Widget">&times;</button>'
                    f'  </div>'
                    f'  <div class="widget-card-ref">field: <code>{w_ref}</code></div>'
                    f'</div>'
                )

            groups_html.append(
                f'<div class="designer-group-card" data-group="{g_name}">'
                f'  <div class="group-header">'
                f'    <h4>{g_title} <span class="dim-label">({g_name})</span></h4>'
                f'    <div class="group-controls">'
                f'      <button type="button" class="btn-xs btn-add-widget">+ Add Widget</button>'
                f'    </div>'
                '  </div>'
                f'  <div class="widgets-container">' + "".join(widgets_html) + '</div>'
                '</div>'
            )

        panels_canvas_html.append(
            f'<div class="designer-panel-card" data-panel="{p_name}">'
            f'  <div class="panel-header">'
            f'    <h3>{p_title}</h3>'
            '  </div>'
            f'  <div class="groups-container">' + "".join(groups_html) + '</div>'
            '</div>'
        )

    commands_rendered = "".join(commands_html)
    telemetry_rendered = "".join(telemetry_html)
    canvas_rendered = "".join(panels_canvas_html)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:;">
  <title>Device UI Designer - {safe_title}</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-header: #334155;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --border: #334155;
      --danger: #ef4444;
      --success: #10b981;
      --warning: #f59e0b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: var(--card-bg);
      border-bottom: 1px solid var(--border);
      padding: 0.75rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-shrink: 0;
    }}
    .header-title {{ display: flex; align-items: center; gap: 0.75rem; }}
    .header-title h1 {{ font-size: 1.25rem; font-weight: 600; }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      font-size: 0.75rem;
      border-radius: 4px;
      background: var(--border);
      font-weight: 500;
    }}
    .badge-read_only {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
    .badge-idempotent {{ background: rgba(56, 189, 248, 0.2); color: #38bdf8; }}
    .badge-mutating {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    .badge-destructive {{ background: rgba(239, 68, 68, 0.3); color: #ef4444; font-weight: 700; }}
    .badge-info {{ background: rgba(56, 189, 248, 0.2); color: #38bdf8; }}
    .toolbar {{ display: flex; gap: 0.5rem; }}
    .btn {{
      background: var(--card-header);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 500;
      transition: all 0.15s ease;
    }}
    .btn:hover {{ background: #475569; }}
    .btn-primary {{ background: var(--accent); color: #0f172a; border-color: var(--accent); }}
    .btn-primary:hover {{ background: var(--accent-hover); }}
    .btn-xs {{
      padding: 2px 8px;
      font-size: 0.75rem;
      border-radius: 4px;
      background: var(--card-header);
      color: var(--text);
      border: 1px solid var(--border);
      cursor: pointer;
    }}
    .btn-xs:hover {{ background: var(--accent); color: #0f172a; }}
    .btn-icon {{ background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 1.1rem; }}
    .btn-icon:hover {{ color: var(--danger); }}
    .designer-layout {{
      display: grid;
      grid-template-columns: 280px 1fr 300px;
      flex: 1;
      overflow: hidden;
    }}
    .sidebar {{
      background: var(--card-bg);
      border-right: 1px solid var(--border);
      overflow-y: auto;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}
    .sidebar-right {{
      border-right: none;
      border-left: 1px solid var(--border);
    }}
    .canvas {{
      background: var(--bg);
      overflow-y: auto;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }}
    .section-title {{
      font-size: 0.85rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      margin-bottom: 0.5rem;
    }}
    .protocol-item {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 10px;
      margin-bottom: 6px;
    }}
    .item-header {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; }}
    .item-meta {{ font-size: 0.75rem; color: var(--text-muted); margin-top: 2px; }}
    .item-actions {{ display: flex; gap: 4px; margin-top: 6px; }}
    .designer-panel-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
    }}
    .panel-header h3 {{ font-size: 1.1rem; margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    .designer-group-card {{
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .group-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
    }}
    .dim-label {{ color: var(--text-muted); font-size: 0.8rem; font-weight: normal; }}
    .widgets-container {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 0.75rem;
    }}
    .designer-widget-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 12px;
      cursor: pointer;
      transition: border-color 0.15s ease;
    }}
    .designer-widget-card:hover, .designer-widget-card.selected {{
      border-color: var(--accent);
    }}
    .widget-card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 4px;
    }}
    .widget-type-badge {{
      font-size: 0.65rem;
      padding: 1px 4px;
      background: var(--border);
      border-radius: 3px;
      font-weight: bold;
      color: var(--accent);
    }}
    .widget-label {{ font-size: 0.85rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .widget-card-ref {{ font-size: 0.7rem; color: var(--text-muted); margin-top: 4px; }}
    .widget-card-ref code {{ color: #a5f3fc; }}
    .widget-card-ref.safety {{ color: var(--warning); }}
    .designer-group-card.target {{ border-color: var(--accent); }}
    .widgets-container.drop {{ outline: 2px dashed var(--accent); }}
    .panel-header {{ display: flex; justify-content: space-between; align-items: baseline; }}
    .prop-row {{ margin-bottom: 0.75rem; }}
    .prop-row label {{ display: block; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px; }}
    .prop-row input, .prop-row select {{
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 8px;
      border-radius: 4px;
      font-size: 0.85rem;
    }}
    .modal {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(4px);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }}
    .modal-content {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      width: 80%;
      max-width: 900px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .modal-header {{
      padding: 1rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .modal-body {{ padding: 1rem; overflow-y: auto; flex: 1; }}
    .modal-body pre {{ background: var(--bg); padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.85rem; }}
  </style>
</head>
<body>
  <header>
    <div class="header-title">
      <h1>OmniUART UI Designer</h1>
      <span class="badge badge-info">{safe_proto} v{safe_version}</span>
      <span class="dim-label">Vendor: {safe_vendor}</span>
    </div>
    <div class="toolbar">
      <button type="button" class="btn" id="btn-add-panel">+ Panel</button>
      <button type="button" class="btn" id="btn-validate">Validate Compatibility</button>
      <button type="button" class="btn" id="btn-preview">Live Preview</button>
      <button type="button" class="btn" id="btn-export-yaml">Export YAML</button>
      <button type="button" class="btn" id="btn-export-json">Export JSON</button>
      <button type="button" class="btn btn-primary" id="btn-save">Save Definition</button>
    </div>
  </header>

  <div class="designer-layout">
    <!-- Left Sidebar: Protocol Fields and Commands -->
    <aside class="sidebar">
      <div>
        <h3 class="section-title">Commands ({len(protocol.commands)})</h3>
        <div id="protocol-commands">{commands_rendered}</div>
      </div>
      <div>
        <h3 class="section-title">Telemetry Fields</h3>
        <div id="protocol-telemetry">{telemetry_rendered}</div>
      </div>
    </aside>

    <!-- Center Canvas: Visual UI Workspace -->
    <main class="canvas" id="canvas-area">
      {canvas_rendered}
    </main>

    <!-- Right Sidebar: Property Inspector -->
    <aside class="sidebar sidebar-right" id="property-inspector">
      <h3 class="section-title">Widget Inspector</h3>
      <p id="inspector-placeholder" class="dim-label">Select a widget card from the canvas to edit its properties.</p>
      <div id="inspector-form" style="display: none;">
        <div class="prop-row">
          <label>Field Reference</label>
          <input type="text" id="prop-ref" readonly style="opacity: 0.8;">
        </div>
        <div class="prop-row">
          <label>Display Label</label>
          <input type="text" id="prop-label">
        </div>
        <div class="prop-row">
          <label>Widget Type</label>
          <select id="prop-type">
            <option value="slider">Slider</option>
            <option value="switch">Switch</option>
            <option value="dropdown">Dropdown</option>
            <option value="gauge">Gauge</option>
            <option value="line_plot">Line Plot</option>
            <option value="badge">Badge</option>
            <option value="text">Text Display</option>
            <option value="number_input">Number Input</option>
            <option value="text_input">Text Input</option>
            <option value="button">Action Button</option>
            <option value="file_transfer">File Transfer</option>
            <option value="firmware_update">Firmware Update</option>
          </select>
        </div>
        <div class="prop-row">
          <label>Unit</label>
          <input type="text" id="prop-unit" placeholder="e.g. mV, RPM, °C">
        </div>
        <div class="prop-row">
          <label>Min / Max / Step</label>
          <div style="display: flex; gap: 4px;">
            <input type="number" id="prop-min" placeholder="Min" style="width: 33%;">
            <input type="number" id="prop-max" placeholder="Max" style="width: 33%;">
            <input type="number" id="prop-step" placeholder="Step" style="width: 33%;">
          </div>
        </div>
        <div class="prop-row" id="safety-section" style="display: none;">
          <label>Safety rule</label>
          <p class="dim-label" id="prop-safety-level"></p>
          <label><input type="checkbox" id="prop-confirm" style="width: auto;"> Require confirmation</label>
          <label><input type="checkbox" id="prop-danger" style="width: auto;"> Danger zone</label>
          <input type="text" id="prop-warning" placeholder="Warning message">
        </div>
        <div class="prop-row">
          <button type="button" class="btn btn-primary" id="btn-apply-props" style="width: 100%;">Apply Changes</button>
        </div>
      </div>
    </aside>
  </div>

  <!-- Export / Modal Dialog -->
  <div class="modal" id="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h3 id="modal-title">Export Specification</h3>
        <button type="button" class="btn-icon" id="btn-close-modal">&times;</button>
      </div>
      <div class="modal-body" id="modal-body">
        <pre><code id="modal-code"></code></pre>
      </div>
    </div>
  </div>

  <script type="application/json" id="initial-data">{json_blob}</script>
  <script>{_DESIGNER_SCRIPT}</script>
</body>
</html>
"""
