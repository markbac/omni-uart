"""Catalog Manager for auto-discovering protocol definitions and test scripts."""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from omniuart.core.models import ProtocolSpec, ScriptSpec, load_protocol, load_script

logger = logging.getLogger(__name__)


PROTOCOL_PATH_ENV = "OMNIUART_PROTOCOL_PATH"
SCRIPT_PATH_ENV = "OMNIUART_SCRIPT_PATH"


def _env_dirs(name: str) -> List[Path]:
    """Directories listed in environment variable ``name`` (separated by ``os.pathsep``)."""
    return [Path(part) for part in os.environ.get(name, "").split(os.pathsep) if part.strip()]


def _same_content(a: Path, b: Path) -> bool:
    try:
        return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
    except OSError:
        return False


class CatalogManager:
    """Manages auto-discovery, cataloging, and retrieval of protocol definitions and test scripts.

    Where definitions are searched, highest precedence first:

    1. ``protocol_dirs`` / ``script_dirs`` passed to the constructor (only these are searched);
    2. the ``OMNIUART_PROTOCOL_PATH`` / ``OMNIUART_SCRIPT_PATH`` environment variables
       (directories separated by ``os.pathsep``);
    3. the default locations that exist: ``examples/protocols``, ``protocols`` and ``schemas`` (scripts:
       ``examples/scripts`` and ``scripts``) under the current directory, and under the executable's
       directory when running as a frozen binary.

    Within the search order the first directory wins: a file with the same name in a later directory is
    shadowed, and every such shadowing is recorded in :attr:`collisions` and logged. Explicitly excludes
    G460 files as required by system policy.
    """

    def __init__(
        self,
        protocol_dirs: Optional[List[Union[str, Path]]] = None,
        script_dirs: Optional[List[Union[str, Path]]] = None,
    ) -> None:
        self.protocol_dirs: List[Path] = []
        self.script_dirs: List[Path] = []
        self.collisions: List[Dict[str, Any]] = []

        # Resolve binary directory if running as standalone frozen binary or script
        exe_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        bases = [exe_dir] if exe_dir == Path.cwd() else [exe_dir, Path.cwd()]

        default_proto_dirs = [b / sub for b in bases for sub in ("schemas", "examples/protocols", "protocols")]
        default_script_dirs = [b / sub for b in bases for sub in ("examples/scripts", "scripts")]

        for pd in protocol_dirs or _env_dirs(PROTOCOL_PATH_ENV) or default_proto_dirs:
            if protocol_dirs or Path(pd).is_dir():
                self.add_protocol_dir(pd)
        for sd in script_dirs or _env_dirs(SCRIPT_PATH_ENV) or default_script_dirs:
            if script_dirs or Path(sd).is_dir():
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

    def _scan(self, directories: List[Path], excluded: Callable[[Path], bool], kind: str) -> List[Path]:
        """Files in precedence order; a file shadowed by an earlier one of the same name is recorded, not used."""
        chosen: Dict[str, Path] = {}
        for directory in directories:
            if not directory.is_dir():
                continue
            for file_path in sorted(directory.glob("*.*"), key=lambda f: f.name):
                if file_path.suffix.lower() not in (".json", ".yaml", ".yml") or excluded(file_path):
                    continue
                key = file_path.name.lower()
                if key not in chosen:
                    chosen[key] = file_path
                    continue
                entry = {
                    "kind": kind,
                    "reason": "same filename",
                    "name": file_path.name,
                    "used": str(chosen[key]),
                    "shadowed": str(file_path),
                    "identical": _same_content(chosen[key], file_path),
                }
                if entry not in self.collisions:
                    self.collisions.append(entry)
                    logger.warning(
                        "%s '%s' in %s is shadowed by %s (%s)", kind, file_path.name, file_path.parent,
                        chosen[key].parent, "identical content" if entry["identical"] else "DIFFERENT content",
                    )
        return sorted(chosen.values(), key=lambda f: (f.name.lower(), str(f)))

    def list_protocol_files(self) -> List[Path]:
        """Protocol definition files in deterministic order (excluding G460 and meta-schemas)."""
        return self._scan(
            self.protocol_dirs,
            lambda f: "g460" in f.name.lower() or "schema.json" in f.name.lower(),
            "protocol",
        )

    def list_script_files(self) -> List[Path]:
        """Test script files in deterministic order (excluding G460)."""
        return self._scan(self.script_dirs, lambda f: "g460" in f.name.lower(), "script")

    def name_collisions(self) -> List[Dict[str, Any]]:
        """Protocols (different files) that declare the same ``metadata.name``; lookups by name use the first."""
        by_name: Dict[str, List[Path]] = {}
        for pf in self.list_protocol_files():
            try:
                by_name.setdefault(load_protocol(pf).metadata.name.lower(), []).append(pf)
            except Exception:  # noqa: BLE001 - unloadable files are reported by catalog_summary
                continue
        return [
            {"kind": "protocol", "reason": "same protocol name", "name": name, "used": str(files[0]), "shadowed": [str(f) for f in files[1:]]}
            for name, files in sorted(by_name.items())
            if len(files) > 1
        ]

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

    def resolve_script_protocol(self, script: ScriptSpec, override: Optional[str] = None) -> Optional[ProtocolSpec]:
        """Find the protocol a script targets: ``override``, else ``meta.protocol`` as a catalog name or a file path."""
        ref_path = Path(script.meta.protocol)
        for ref in [override] if override else [script.meta.protocol, ref_path.name, ref_path.stem]:
            if not ref:
                continue
            if Path(ref).is_file():
                try:
                    return load_protocol(Path(ref))
                except ValueError:
                    return None
            spec = self.get_protocol(ref)
            if spec:
                return spec
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
                script = load_script(sf)
                scripts.append({
                    "filename": sf.name,
                    "path": str(sf),
                    "name": script.meta.name,
                    "protocol": script.meta.protocol,
                    "steps_count": len(script.steps),
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
            "collisions": self.collisions + self.name_collisions(),
        }
