"""Protocol Adapter & Plugin Architecture for OmniUART (#219).

Provides extensible plugin hooks for custom data encodings, checksum algorithms,
message identification rules, dynamic field converters, and protocol importers/exporters.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from omniuart.core.models import FieldSpec, ProtocolSpec

logger = logging.getLogger(__name__)

EncoderFn = Callable[[Any], bytes]
DecoderFn = Callable[[bytes], Any]
ChecksumFn = Callable[[bytes], int]
ImporterFn = Callable[[str], ProtocolSpec]
ExporterFn = Callable[[ProtocolSpec], str]


class ProtocolPlugin:
    """Base class or container for protocol-specific extension plugins."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.encodings: Dict[str, Tuple[EncoderFn, DecoderFn]] = {}
        self.checksums: Dict[str, ChecksumFn] = {}
        self.importers: Dict[str, ImporterFn] = {}
        self.exporters: Dict[str, ExporterFn] = {}


class PluginRegistry:
    """Central registry managing custom encodings, checksums, importers and exporters."""

    def __init__(self) -> None:
        self._encodings: Dict[str, Tuple[EncoderFn, DecoderFn]] = {}
        self._checksums: Dict[str, ChecksumFn] = {}
        self._importers: Dict[str, ImporterFn] = {}
        self._exporters: Dict[str, ExporterFn] = {}
        self._plugins: Dict[str, ProtocolPlugin] = {}

    def register_plugin(self, plugin: ProtocolPlugin) -> None:
        """Register a full ProtocolPlugin bundle."""
        self._plugins[plugin.name] = plugin
        for name, (enc, dec) in plugin.encodings.items():
            self.register_encoding(name, enc, dec)
        for name, fn in plugin.checksums.items():
            self.register_checksum(name, fn)
        for fmt, fn in plugin.importers.items():
            self.register_importer(fmt, fn)
        for fmt, fn in plugin.exporters.items():
            self.register_exporter(fmt, fn)
        logger.info("Registered ProtocolPlugin '%s'", plugin.name)

    def register_encoding(self, name: str, encoder: EncoderFn, decoder: DecoderFn) -> None:
        self._encodings[name.lower().strip()] = (encoder, decoder)

    def get_encoding(self, name: str) -> Optional[Tuple[EncoderFn, DecoderFn]]:
        return self._encodings.get(name.lower().strip())

    def register_checksum(self, name: str, fn: ChecksumFn) -> None:
        self._checksums[name.lower().strip()] = fn

    def get_checksum(self, name: str) -> Optional[ChecksumFn]:
        return self._checksums.get(name.lower().strip())

    def register_importer(self, format_name: str, fn: ImporterFn) -> None:
        self._importers[format_name.lower().strip()] = fn

    def get_importer(self, format_name: str) -> Optional[ImporterFn]:
        return self._importers.get(format_name.lower().strip())

    def register_exporter(self, format_name: str, fn: ExporterFn) -> None:
        self._exporters[format_name.lower().strip()] = fn

    def get_exporter(self, format_name: str) -> Optional[ExporterFn]:
        return self._exporters.get(format_name.lower().strip())


# Global singleton plugin registry
plugin_registry = PluginRegistry()
