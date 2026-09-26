"""Catalog Manager for auto-discovering protocol definitions and test scripts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from omniuart.core.models import ProtocolSpec, ScriptSpec, load_protocol, load_script

logger = logging.getLogger(__name__)


class CatalogManager:
    """Manages auto-discovery, cataloging, and retrieval of protocol definitions and test scripts.
    
    Automatically picks up new protocol definitions and scripts added to registered directories.
    Explicitly excludes G460 files as required by system policy.
    """

    def __init__(
        self,
        protocol_dirs: Optional[List[Union[str, Path]]] = None,
        script_dirs: Optional[List[Union[str, Path]]] = None,
    ) -> None:
        self.protocol_dirs: List[Path] = []
        self.script_dirs: List[Path] = []

        # Default paths to check
        default_proto_dirs = [
            Path("examples/protocols"),
            Path("../uart-interface-schema-kit/kit/examples"),
            Path("d:/Antigravity/omniUart/uart-interface-schema-kit/kit/examples"),
        ]
        default_script_dirs = [
            Path("examples/scripts"),
            Path("../uart-interface-schema-kit/kit/examples/sequences"),
            Path("d:/Antigravity/omniUart/uart-interface-schema-kit/kit/examples/sequences"),
        ]

        if protocol_dirs:
            for pd in protocol_dirs:
                self.add_protocol_dir(pd)
        else:
            for pd in default_proto_dirs:
                if pd.exists() and pd.is_dir():
                    self.add_protocol_dir(pd)

        if script_dirs:
            for sd in script_dirs:
                self.add_script_dir(sd)
        else:
            for sd in default_script_dirs:
                if sd.exists() and sd.is_dir():
                    self.add_script_dir(sd)

    def add_protocol_dir(self, directory: Union[str, Path]) -> None:
        """Register a directory to scan for protocol definitions."""
        p = Path(directory).resolve()
        if p not in self.protocol_dirs:
            self.protocol_dirs.append(p)

    def add_script_dir(self, directory: Union[str, Path]) -> None:
        """Register a directory to scan for test scripts."""
        s = Path(directory).resolve()
        if s not in self.script_dirs:
            self.script_dirs.append(s)

    def list_protocol_files(self) -> List[Path]:
        """Scan all registered protocol directories and return valid protocol file paths (excluding G460)."""
        files: List[Path] = []
        seen_names: Set[str] = set()

        for p_dir in self.protocol_dirs:
            if not p_dir.exists():
                continue
            for file_path in p_dir.glob("*.*"):
                if file_path.suffix.lower() not in (".json", ".yaml", ".yml"):
                    continue
                if "g460" in file_path.name.lower():
                    continue
                if file_path.name not in seen_names:
                    seen_names.add(file_path.name)
                    files.append(file_path)

        return sorted(files, key=lambda f: f.name)

    def list_script_files(self) -> List[Path]:
        """Scan all registered script directories and return valid script file paths (excluding G460)."""
        files: List[Path] = []
        seen_names: Set[str] = set()

        for s_dir in self.script_dirs:
            if not s_dir.exists():
                continue
            for file_path in s_dir.glob("*.*"):
                if file_path.suffix.lower() not in (".json", ".yaml", ".yml"):
                    continue
                if "g460" in file_path.name.lower():
                    continue
                if file_path.name not in seen_names:
                    seen_names.add(file_path.name)
                    files.append(file_path)

        return sorted(files, key=lambda f: f.name)

    def get_protocol(self, identifier: str) -> Optional[ProtocolSpec]:
        """Lookup and parse a protocol definition by filename, protocol name, or partial match."""
        files = self.list_protocol_files()
        
        # 1. Direct filename match
        for f in files:
            if f.name.lower() == identifier.lower() or f.stem.lower() == identifier.lower():
                try:
                    return load_protocol(f)
                except ValueError:
                    return None

        # 2. Match by protocol title/name
        for f in files:
            try:
                spec = load_protocol(f)
                if spec.metadata.name.lower() == identifier.lower():
                    return spec
            except Exception:
                continue

        # 3. Partial substring match
        for f in files:
            if identifier.lower() in f.name.lower():
                try:
                    return load_protocol(f)
                except Exception:
                    continue

        return None

    def get_script(self, identifier: str) -> Optional[ScriptSpec]:
        """Lookup and parse a test script by filename, script name, or partial match."""
        files = self.list_script_files()

        # 1. Direct filename match
        for f in files:
            if f.name.lower() == identifier.lower() or f.stem.lower() == identifier.lower():
                try:
                    return load_script(f)
                except ValueError:
                    return None

        # 2. Match by script meta name
        for f in files:
            try:
                spec = load_script(f)
                if spec.meta.name.lower() == identifier.lower():
                    return spec
            except Exception:
                continue

        # 3. Partial substring match
        for f in files:
            if identifier.lower() in f.name.lower():
                try:
                    return load_script(f)
                except Exception:
                    continue

        return None

    def catalog_summary(self) -> Dict[str, Any]:
        """Return a summary of all discovered protocols and test scripts."""
        protos = []
        for pf in self.list_protocol_files():
            try:
                spec = load_protocol(pf)
                protos.append({
                    "filename": pf.name,
                    "path": str(pf),
                    "name": spec.metadata.name,
                    "version": spec.metadata.version,
                    "commands_count": len(spec.commands),
                    "baudrate": spec.serial_config.baudrate,
                })
            except Exception as e:
                logger.warning(f"Could not load protocol file {pf}: {e}")

        scripts = []
        for sf in self.list_script_files():
            try:
                spec = load_script(sf)
                scripts.append({
                    "filename": sf.name,
                    "path": str(sf),
                    "name": spec.meta.name,
                    "protocol": spec.meta.protocol,
                    "steps_count": len(spec.steps),
                })
            except Exception as e:
                logger.warning(f"Could not load script file {sf}: {e}")

        return {
            "protocol_directories": [str(d) for d in self.protocol_dirs],
            "script_directories": [str(d) for d in self.script_dirs],
            "protocols_found": len(protos),
            "scripts_found": len(scripts),
            "protocols": protos,
            "scripts": scripts,
        }
