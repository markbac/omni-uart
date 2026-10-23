"""Device Explorer & Dynamic Device Navigation Subsystem (#232).

Provides a device-centric navigation model with device discovery, connection state, and logical sections
(Overview, Connectivity, Metering, Configuration, Diagnostics, Firmware) dynamically generated
from device capabilities and protocol specifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from omniuart.core.catalog import CatalogManager
from omniuart.core.device_ui import DeviceUISpec
from omniuart.core.models import CommandSafety, ProtocolSpec


class DeviceSection(str, Enum):
    """Logical device navigation sections."""

    OVERVIEW = "overview"
    CONNECTIVITY = "connectivity"
    METERING = "metering"
    CONFIGURATION = "configuration"
    DIAGNOSTICS = "diagnostics"
    FIRMWARE = "firmware"


@dataclass
class NavigationNode:
    """A logical navigation node / section in the Device Explorer."""

    section: DeviceSection
    title: str
    icon: str
    commands: List[str] = field(default_factory=list)
    telemetry: List[str] = field(default_factory=list)


@dataclass
class DeviceNode:
    """Discovered or active target device entity in Device Explorer."""

    id: str
    name: str
    protocol_name: str
    connection_state: str = "disconnected"  # connected, disconnected, error
    port_or_address: Optional[str] = None
    navigation_tree: List[NavigationNode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "protocol_name": self.protocol_name,
            "connection_state": self.connection_state,
            "port_or_address": self.port_or_address,
            "sections": [
                {
                    "section": nav.section.value,
                    "title": nav.title,
                    "icon": nav.icon,
                    "commands_count": len(nav.commands),
                    "telemetry_count": len(nav.telemetry),
                }
                for nav in self.navigation_tree
            ],
        }


def build_navigation_tree_from_spec(spec: ProtocolSpec, ui_spec: Optional[DeviceUISpec] = None) -> List[NavigationNode]:
    """Dynamically generate logical navigation sections based on protocol capabilities (#232)."""
    tree: List[NavigationNode] = []

    # 1. Overview section (always included)
    tree.append(NavigationNode(
        section=DeviceSection.OVERVIEW,
        title="Overview & Identity",
        icon="info",
        commands=[c.name for c in spec.commands if c.safety is CommandSafety.READ_ONLY],
        telemetry=[t.name for t in spec.telemetry],
    ))

    # 2. Connectivity section
    tree.append(NavigationNode(
        section=DeviceSection.CONNECTIVITY,
        title="Serial Link & Transport",
        icon="network",
    ))

    # 3. Metering / Telemetry section (if protocol has telemetry or read_only commands)
    metering_cmds = [c.name for c in spec.commands if any(t in c.name.lower() for t in ("read", "get", "measure", "meter"))]
    if spec.telemetry or metering_cmds:
        tree.append(NavigationNode(
            section=DeviceSection.METERING,
            title="Telemetry & Metering",
            icon="gauge",
            commands=metering_cmds,
            telemetry=[t.name for t in spec.telemetry],
        ))

    # 4. Configuration section (for mutating/idempotent set/config commands)
    config_cmds = [c.name for c in spec.commands if c.safety in (CommandSafety.IDEMPOTENT, CommandSafety.MUTATING)]
    if config_cmds:
        tree.append(NavigationNode(
            section=DeviceSection.CONFIGURATION,
            title="Device Configuration",
            icon="settings",
            commands=config_cmds,
        ))

    # 5. Diagnostics section
    diag_cmds = [c.name for c in spec.commands if any(d in c.name.lower() for d in ("ping", "test", "diag", "health", "reset", "clear"))]
    tree.append(NavigationNode(
        section=DeviceSection.DIAGNOSTICS,
        title="Diagnostics & Self-Test",
        icon="activity",
        commands=diag_cmds,
    ))

    # 6. Firmware section (if firmware/bootloader/upgrade mentioned)
    fw_cmds = [c.name for c in spec.commands if any(f in c.name.lower() for f in ("firmware", "boot", "flash", "update", "upgrade"))]
    if fw_cmds:
        tree.append(NavigationNode(
            section=DeviceSection.FIRMWARE,
            title="Firmware & Bootloader",
            icon="cpu",
            commands=fw_cmds,
        ))

    return tree


class DeviceExplorer:
    """Device discovery, connection tracking, and navigation hierarchy manager."""

    def __init__(self, catalog: Optional[CatalogManager] = None) -> None:
        self.catalog = catalog or CatalogManager()
        self.active_devices: Dict[str, DeviceNode] = {}

    def discover_catalog_devices(self) -> List[DeviceNode]:
        """Discover available devices from protocol definition catalog."""
        nodes: List[DeviceNode] = []
        for pf in self.catalog.list_protocol_files():
            try:
                spec = self.catalog._load_protocol_cached(pf)
                dev_id = spec.metadata.name.lower().replace(" ", "_")
                nav_tree = build_navigation_tree_from_spec(spec)
                node = DeviceNode(
                    id=dev_id,
                    name=spec.metadata.name,
                    protocol_name=spec.metadata.name,
                    connection_state="disconnected",
                    navigation_tree=nav_tree,
                )
                nodes.append(node)
            except Exception:
                continue
        return nodes

    def register_active_device(
        self,
        device_id: str,
        spec: ProtocolSpec,
        port_or_address: Optional[str] = None,
        connection_state: str = "connected",
    ) -> DeviceNode:
        """Register or update an active device connection."""
        nav_tree = build_navigation_tree_from_spec(spec)
        node = DeviceNode(
            id=device_id,
            name=spec.metadata.name,
            protocol_name=spec.metadata.name,
            connection_state=connection_state,
            port_or_address=port_or_address,
            navigation_tree=nav_tree,
        )
        self.active_devices[device_id] = node
        return node


    def get_active_device(self, device_id: str) -> Optional[DeviceNode]:
        """Get an active registered device by id (#239)."""
        return self.active_devices.get(device_id)

    def list_active_devices(self) -> List[DeviceNode]:
        """List all actively tracked devices (#239)."""
        return list(self.active_devices.values())

    def remove_active_device(self, device_id: str) -> bool:
        """Remove an active device from tracking (#239)."""
        if device_id in self.active_devices:
            del self.active_devices[device_id]
            return True
        return False

    def compare_devices(self, id_a: str, id_b: str) -> Dict[str, Any]:
        """Generate comparison view between two active devices (#240)."""
        dev_a = self.get_active_device(id_a)
        dev_b = self.get_active_device(id_b)

        if not dev_a or not dev_b:
            missing = id_a if not dev_a else id_b
            return {"error": f"Device '{missing}' not found for comparison"}

        cmds_a = set()
        telemetry_a = set()
        for node in dev_a.navigation_tree:
            cmds_a.update(node.commands)
            telemetry_a.update(node.telemetry)

        cmds_b = set()
        telemetry_b = set()
        for node in dev_b.navigation_tree:
            cmds_b.update(node.commands)
            telemetry_b.update(node.telemetry)

        common_commands = sorted(cmds_a.intersection(cmds_b))
        unique_to_a = sorted(cmds_a - cmds_b)
        unique_to_b = sorted(cmds_b - cmds_a)

        return {
            "device_a": dev_a.to_dict(),
            "device_b": dev_b.to_dict(),
            "same_protocol": dev_a.protocol_name == dev_b.protocol_name,
            "commands_comparison": {
                "common_count": len(common_commands),
                "common": common_commands,
                "unique_a_count": len(unique_to_a),
                "unique_a": unique_to_a,
                "unique_b_count": len(unique_to_b),
                "unique_b": unique_to_b,
            },
            "telemetry_comparison": {
                "common_count": len(telemetry_a.intersection(telemetry_b)),
                "common": sorted(telemetry_a.intersection(telemetry_b)),
            },
            "connection_status_a": dev_a.connection_state,
            "connection_status_b": dev_b.connection_state,
        }
