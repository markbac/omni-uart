"""Catalog Manager for auto-discovering protocol definitions and test scripts."""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from omniuart.core.models import ProtocolSpec, ScriptSpec, load_protocol, load_script

logger = logging.getLogger(__name__)


PROTOCOL_PATH_ENV = "OMNIUART_PROTOCOL_PATH"
SCRIPT_PATH_ENV = "OMNIUART_SCRIPT_PATH"
DEFAULT_IGNORED_PATTERNS = ["g460", "schema.json"]


def _env_dirs(name: str) -> List[Path]:
    """Directories listed in environment variable ``name`` (separated by ``os.pathsep``)."""
    return [Path(part) for part in os.environ.get(name, "").split(os.pathsep) if part.strip()]


def _same_content(a: Path, b: Path) -> bool:
    try:
        return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
    except OSError:
        return False


class CatalogManager:
    """Manages auto-discovery, cataloging, caching, and retrieval of protocol definitions and test scripts.

    Where definitions are searched, highest precedence first:

    1. ``protocol_dirs`` / ``script_dirs`` passed to the constructor (only these are searched);
    2. the ``OMNIUART_PROTOCOL_PATH`` / ``OMNIUART_SCRIPT_PATH`` environment variables
       (directories separated by ``os.pathsep``);
    3. the default locations that exist: ``examples/protocols``, ``protocols`` and ``schemas`` (scripts:
       ``examples/scripts`` and ``scripts``) under the current directory, and under the executable's
       directory when running as a frozen binary.

    Within the search order the first directory wins: a file with the same name in a later directory is
    shadowed, and every such shadowing is recorded in :attr:`collisions` and logged.
    """

    def __init__(
        self,
        protocol_dirs: Optional[List[Union[str, Path]]] = None,
        script_dirs: Optional[List[Union[str, Path]]] = None,
        ignored_patterns: Optional[List[str]] = None,
    ) -> None:
        self.protocol_dirs: List[Path] = []
        self.script_dirs: List[Path] = []
        self.collisions: List[Dict[str, Any]] = []
        self.ignored_patterns: List[str] = ignored_patterns if ignored_patterns is not None else list(DEFAULT_IGNORED_PATTERNS)

        self._proto_cache: Dict[Path, Tuple[float, ProtocolSpec]] = {}
        self._script_cache: Dict[Path, Tuple[float, ScriptSpec]] = {}

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

    def _load_protocol_cached(self, path: Path) -> ProtocolSpec:
        """Load protocol with mtime-based in-memory caching."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0

        if path in self._proto_cache:
            cached_mtime, cached_spec = self._proto_cache[path]
            if cached_mtime == mtime:
                return cached_spec

        spec = load_protocol(path)
        self._proto_cache[path] = (mtime, spec)
        return spec

    def _load_script_cached(self, path: Path) -> ScriptSpec:
        """Load script with mtime-based in-memory caching."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0.0

        if path in self._script_cache:
            cached_mtime, cached_spec = self._script_cache[path]
            if cached_mtime == mtime:
                return cached_spec

        script = load_script(path)
        self._script_cache[path] = (mtime, script)
        return script

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

    def _is_ignored(self, path: Path) -> bool:
        name_lower = path.name.lower()
        for pat in self.ignored_patterns:
            if pat.lower() in name_lower:
                logger.debug("Skipping file '%s' matching ignored pattern '%s'", path.name, pat)
                return True
        return False

    def _scan(self, directories: List[Path], kind: str) -> List[Path]:
        """Files in precedence order; a file shadowed by an earlier one of the same name is recorded, not used."""
        chosen: Dict[str, Path] = {}
        for directory in directories:
            if not directory.is_dir():
                continue
            for file_path in sorted(directory.glob("*.*"), key=lambda f: f.name):
                if file_path.suffix.lower() not in (".json", ".yaml", ".yml") or self._is_ignored(file_path):
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
        """Protocol definition files in deterministic order (excluding ignored patterns)."""
        return self._scan(self.protocol_dirs, "protocol")

    def list_script_files(self) -> List[Path]:
        """Test script files in deterministic order (excluding ignored patterns)."""
        return self._scan(self.script_dirs, "script")

    def name_collisions(self) -> List[Dict[str, Any]]:
        """Protocols (different files) that declare the same ``metadata.name``; lookups by name use the first."""
        by_name: Dict[str, List[Path]] = {}
        for pf in self.list_protocol_files():
            try:
                spec = self._load_protocol_cached(pf)
                by_name.setdefault(spec.metadata.name.lower(), []).append(pf)
            except Exception as exc:  # noqa: BLE001 - unloadable files are reported by catalog_summary
                logger.warning("Error checking name collision for %s: %s", pf, exc)
                continue
        return [
            {"kind": "protocol", "reason": "same protocol name", "name": name, "used": str(files[0]), "shadowed": [str(f) for f in files[1:]]}
            for name, files in sorted(by_name.items())
            if len(files) > 1
        ]

    def get_protocol(self, identifier: str, first: bool = False) -> Optional[ProtocolSpec]:
        """Lookup and parse a protocol definition by filename, protocol name, or partial match.

        Raises ValueError if identifier is ambiguous (matches multiple files) unless first=True.
        """
        if not identifier or not identifier.strip():
            return None

        ident = identifier.strip().lower()
        files = self.list_protocol_files()

        # 1. Direct filename or stem match
        for f in files:
            if f.name.lower() == ident or f.stem.lower() == ident:
                try:
                    return self._load_protocol_cached(f)
                except Exception as exc:
                    logger.warning("Failed loading protocol file %s: %s", f, exc)
                    return None

        # 2. Match by protocol title/name
        title_matches: List[Tuple[Path, ProtocolSpec]] = []
        for f in files:
            try:
                spec = self._load_protocol_cached(f)
                if spec.metadata.name.lower() == ident:
                    title_matches.append((f, spec))
            except Exception as exc:
                logger.warning("Could not parse protocol %s during lookup: %s", f, exc)
                continue

        if len(title_matches) == 1:
            return title_matches[0][1]
        elif len(title_matches) > 1:
            matching_names = [f.name for f, _ in title_matches]
            if first:
                logger.warning("Ambiguous protocol title '%s' matched %s; selecting first", identifier, matching_names)
                return title_matches[0][1]
            raise ValueError(f"Ambiguous protocol title '{identifier}' matches multiple files: {matching_names}. Specify exact filename or use --first.")

        # 3. Partial substring match
        partial_matches: List[Tuple[Path, ProtocolSpec]] = []
        for f in files:
            if ident in f.name.lower():
                try:
                    spec = self._load_protocol_cached(f)
                    partial_matches.append((f, spec))
                except Exception as exc:
                    logger.warning("Could not parse protocol %s during partial lookup: %s", f, exc)
                    continue

        if len(partial_matches) == 1:
            return partial_matches[0][1]
        elif len(partial_matches) > 1:
            matching_names = [f.name for f, _ in partial_matches]
            if first:
                logger.warning("Ambiguous partial match '%s' matched %s; selecting first", identifier, matching_names)
                return partial_matches[0][1]
            raise ValueError(f"Ambiguous identifier '{identifier}' matches multiple protocol files: {matching_names}. Specify exact filename or use --first.")

        return None

    def resolve_script_protocol(self, script: ScriptSpec, override: Optional[str] = None, first: bool = True) -> Optional[ProtocolSpec]:
        """Find the protocol a script targets: ``override``, else ``meta.protocol`` as a catalog name or a file path."""
        ref_path = Path(script.meta.protocol)
        for ref in [override] if override else [script.meta.protocol, ref_path.name, ref_path.stem]:
            if not ref:
                continue
            if Path(ref).is_file():
                try:
                    return self._load_protocol_cached(Path(ref))
                except Exception as exc:
                    logger.warning("Failed loading script protocol file %s: %s", ref, exc)
                    return None
            try:
                spec = self.get_protocol(ref, first=first)
                if spec:
                    return spec
            except ValueError:
                spec = self.get_protocol(ref, first=True)
                if spec:
                    return spec
        return None

    def get_script(self, identifier: str, first: bool = False) -> Optional[ScriptSpec]:
        """Lookup and parse a test script by filename, script name, or partial match."""
        if not identifier or not identifier.strip():
            return None

        ident = identifier.strip().lower()
        files = self.list_script_files()

        # 1. Direct filename or stem match
        for f in files:
            if f.name.lower() == ident or f.stem.lower() == ident:
                try:
                    return self._load_script_cached(f)
                except Exception as exc:
                    logger.warning("Failed loading script file %s: %s", f, exc)
                    return None

        # 2. Match by script meta name
        name_matches: List[Tuple[Path, ScriptSpec]] = []
        for f in files:
            try:
                spec = self._load_script_cached(f)
                if spec.meta.name.lower() == ident:
                    name_matches.append((f, spec))
            except Exception as exc:
                logger.warning("Could not parse script %s during lookup: %s", f, exc)
                continue

        if len(name_matches) == 1:
            return name_matches[0][1]
        elif len(name_matches) > 1:
            matching_names = [f.name for f, _ in name_matches]
            if first:
                logger.warning("Ambiguous script name '%s' matched %s; selecting first", identifier, matching_names)
                return name_matches[0][1]
            raise ValueError(f"Ambiguous script name '{identifier}' matches multiple files: {matching_names}. Specify exact filename or use --first.")

        # 3. Partial substring match
        partial_matches: List[Tuple[Path, ScriptSpec]] = []
        for f in files:
            if ident in f.name.lower():
                try:
                    spec = self._load_script_cached(f)
                    partial_matches.append((f, spec))
                except Exception as exc:
                    logger.warning("Could not parse script %s during partial lookup: %s", f, exc)
                    continue

        if len(partial_matches) == 1:
            return partial_matches[0][1]
        elif len(partial_matches) > 1:
            matching_names = [f.name for f, _ in partial_matches]
            if first:
                logger.warning("Ambiguous partial match '%s' matched %s; selecting first", identifier, matching_names)
                return partial_matches[0][1]
            raise ValueError(f"Ambiguous identifier '{identifier}' matches multiple script files: {matching_names}. Specify exact filename or use --first.")

        return None

    def catalog_summary(self) -> Dict[str, Any]:
        """Return a summary of all discovered protocols and test scripts."""
        protos = []
        for pf in self.list_protocol_files():
            try:
                spec = self._load_protocol_cached(pf)
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
                script = self._load_script_cached(sf)
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
