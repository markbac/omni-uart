"""Import an AsyncAPI document with ``x-omniuart`` extensions as an OmniUART protocol (#346).

AsyncAPI describes messages and channels, not the wire format, and has no binding for UART links.
The ``x-omniuart`` extension vocabulary (see ``schemas/x-omniuart.schema.json`` and
``docs/specs/asyncapi-serial-mapping.md``) carries what the native protocol format expresses:

- on the document: ``schema_version``, ``serial``, ``framing``, ``error_replies``, ``correlate`` and
  every other protocol-level section;
- on each message: ``kind`` (``command``, ``response`` or ``telemetry``), the message ``id``, command
  ``safety``, ``tags`` and ``correlate``, and for a response the ``command`` it answers, its
  ``timeout_ms`` and text ``success_pattern`` / ``error_patterns``;
- on each payload property: the wire ``type``, ``endian``, length rules, scale and offset, bit
  fields, options and every other field attribute.

:func:`import_asyncapi` returns the same :class:`ProtocolSpec` the native format would, together
with an :class:`ImportReport` listing everything it could not map. Nothing is dropped silently: an
unmappable item is either an error (the import fails and lists every error) or a warning in the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from pydantic import ValidationError

from omniuart.core.models import FieldSpec, ProtocolSpec

EXTENSION = "x-omniuart"
EXTENSION_VERSION = "1.0"

# Protocol-level keys that are not in the document extension because AsyncAPI carries them natively.
_NATIVE_TOP = {"metadata", "commands", "telemetry"}
# JSON Schema ``type`` to a field type, when a property has no ``x-omniuart.type`` (integers and numbers
# need a width, so they cannot be guessed).
_GUESSABLE = {"boolean": "bool", "string": "string"}


class AsyncAPIImportError(ValueError):
    """The document cannot be imported; ``errors`` lists every problem found."""

    def __init__(self, errors: List[str], report: "ImportReport") -> None:
        self.errors = errors
        self.report = report
        lines = "\n".join(f"  - {e}" for e in errors)
        super().__init__(f"AsyncAPI document cannot be imported ({len(errors)} error(s)):\n{lines}")


@dataclass
class ImportReport:
    """What the importer could not map exactly. Errors stop the import; warnings do not."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def error(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def warn(self, where: str, message: str) -> None:
        self.warnings.append(f"{where}: {message}")


def is_asyncapi_document(data: Any) -> bool:
    return isinstance(data, Mapping) and "asyncapi" in data


class _Resolver:
    """Resolves local ``$ref`` pointers (``#/components/...``)."""

    def __init__(self, doc: Mapping[str, Any], report: ImportReport) -> None:
        self.doc = doc
        self.report = report

    def __call__(self, node: Any, where: str, depth: int = 0) -> Any:
        while isinstance(node, Mapping) and "$ref" in node:
            ref = node["$ref"]
            if depth > 32:
                self.report.error(where, f"$ref '{ref}' is circular")
                return {}
            if not isinstance(ref, str) or not ref.startswith("#/"):
                self.report.error(where, f"only local $ref pointers are supported, got '{ref}'")
                return {}
            target: Any = self.doc
            for part in ref[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(target, Mapping) or part not in target:
                    self.report.error(where, f"$ref '{ref}' does not resolve")
                    return {}
                target = target[part]
            node, depth = target, depth + 1
        return node


def _messages(doc: Mapping[str, Any], resolve: _Resolver, report: ImportReport) -> Iterator[Tuple[str, Mapping[str, Any], Optional[str]]]:
    """``(where, message, operation)`` for every message, in document order, each message once.

    ``operation`` is ``publish``/``subscribe`` (AsyncAPI 2) or ``send``/``receive`` (AsyncAPI 3),
    or ``None`` when only ``components.messages`` lists it.
    """
    seen: set[int] = set()

    def expand(message: Any, where: str, op: Optional[str]) -> Iterator[Tuple[str, Mapping[str, Any], Optional[str]]]:
        message = resolve(message, where)
        if not isinstance(message, Mapping):
            return
        if "oneOf" in message:
            for i, item in enumerate(message["oneOf"]):
                yield from expand(item, f"{where}.oneOf[{i}]", op)
            return
        if id(message) in seen:
            return
        seen.add(id(message))
        yield where, message, op

    channels = doc.get("channels") or {}
    major = str(doc.get("asyncapi", "")).split(".", 1)[0]
    if major == "3":
        actions: Dict[str, str] = {}
        for op_name, op in (doc.get("operations") or {}).items():
            op = resolve(op, f"operations.{op_name}")
            channel = resolve(op.get("channel"), f"operations.{op_name}.channel") if isinstance(op, Mapping) else None
            for name, ch in channels.items():
                if resolve(ch, f"channels.{name}") is channel:
                    actions[name] = str(op.get("action"))
        for name, ch in channels.items():
            ch = resolve(ch, f"channels.{name}")
            for key, msg in (ch.get("messages") or {}).items():
                yield from expand(msg, f"channels.{name}.messages.{key}", actions.get(name))
    else:
        for name, ch in channels.items():
            ch = resolve(ch, f"channels.{name}")
            for op in ("publish", "subscribe"):
                if isinstance(ch.get(op), Mapping) and "message" in ch[op]:
                    yield from expand(ch[op]["message"], f"channels.{name}.{op}.message", op)
    for key, msg in ((doc.get("components") or {}).get("messages") or {}).items():
        yield from expand(msg, f"components.messages.{key}", None)


def _field(name: str, schema: Mapping[str, Any], where: str, resolve: _Resolver, report: ImportReport) -> Optional[Dict[str, Any]]:
    """One native field definition from a payload property."""
    schema = resolve(schema, where)
    ext = dict(schema.get(EXTENSION) or {})
    out: Dict[str, Any] = {"name": name}
    if "options" in ext and isinstance(ext["options"], list):
        ext["options"] = {o["value"]: o["label"] for o in ext["options"]}
    out.update(ext)
    if "type" not in out:
        guessed = _GUESSABLE.get(str(schema.get("type")))
        if guessed is None:
            report.error(where, f"no {EXTENSION}.type: a JSON Schema '{schema.get('type')}' does not say how it is sent on the wire")
            return None
        report.warn(where, f"no {EXTENSION}.type, assumed '{guessed}' from the JSON Schema type")
        out["type"] = guessed
    for json_key, native in (("minimum", "min"), ("maximum", "max"), ("default", "default"), ("x-unit", "unit"), ("x-scale", "scale")):
        if json_key in schema and native not in out:
            out[native] = schema[json_key]
    if "enum" in schema and "options" not in out and out["type"] == "enum":
        out["options"] = {v: str(v) for v in schema["enum"]}
    nested = schema.get("properties") if schema.get("type") == "object" else (schema.get("items") or {}).get("properties")
    if nested:
        fields = [_field(n, s, f"{where}.properties.{n}", resolve, report) for n, s in nested.items()]
        out["nested_fields"] = [f for f in fields if f is not None]
    known = set(FieldSpec.model_fields)
    for key in sorted(set(ext) - known):
        report.error(where, f"unknown {EXTENSION} field attribute '{key}'")
        out.pop(key, None)
    return out


def _fields(payload: Any, where: str, resolve: _Resolver, report: ImportReport) -> List[Dict[str, Any]]:
    payload = resolve(payload, where) if payload is not None else {}
    if not payload:
        return []
    if payload.get("type") not in (None, "object"):
        report.error(where, f"payload must be an object schema, got '{payload.get('type')}'")
        return []
    out: List[Dict[str, Any]] = []
    for name, prop in (payload.get("properties") or {}).items():
        prop_resolved = resolve(prop, f"{where}.properties.{name}")
        if (prop_resolved.get(EXTENSION) or {}).get("role") == "command_id":
            continue  # the message id, written by the exporter for readers; it comes from x-omniuart.id
        f = _field(name, prop_resolved, f"{where}.properties.{name}", resolve, report)
        if f is not None:
            out.append(f)
    return out


def _serial(doc: Mapping[str, Any], top: Mapping[str, Any], report: ImportReport) -> Optional[Dict[str, Any]]:
    if isinstance(top.get("serial"), Mapping):
        return dict(top["serial"])
    for name, server in (doc.get("servers") or {}).items():
        binding = ((server or {}).get("bindings") or {}).get("serial") or {}
        if "baudRate" in binding:
            report.warn(f"servers.{name}", f"no {EXTENSION}.serial; serial settings taken from the serial binding")
            out: Dict[str, Any] = {"baudrate": binding["baudRate"]}
            for src, dst in (("dataBits", "bytesize"), ("parity", "parity"), ("stopBits", "stopbits")):
                if src in binding:
                    out[dst] = binding[src]
            return out
    report.error(EXTENSION, "no serial settings: add x-omniuart.serial (baudrate, ...) to the document")
    return None


def import_asyncapi(doc: Mapping[str, Any], source_name: Optional[str] = None) -> Tuple[ProtocolSpec, ImportReport]:
    """Build a :class:`ProtocolSpec` from an AsyncAPI 2.x or 3.x document with ``x-omniuart`` extensions.

    Raises :class:`AsyncAPIImportError` listing every error when the document cannot be mapped.
    """
    report = ImportReport()
    where_doc = source_name or "document"
    if not is_asyncapi_document(doc):
        raise AsyncAPIImportError([f"{where_doc}: not an AsyncAPI document (no 'asyncapi' key)"], report)
    version = str(doc["asyncapi"])
    if version.split(".", 1)[0] not in ("2", "3"):
        report.error("asyncapi", f"version {version} is not supported (2.x or 3.x)")
    resolve = _Resolver(doc, report)
    top = dict(doc.get(EXTENSION) or {})
    ext_version = str(top.pop("version", EXTENSION_VERSION))
    if ext_version.split(".", 1)[0] != EXTENSION_VERSION.split(".", 1)[0]:
        report.error(EXTENSION, f"extension version {ext_version} is not supported (expected {EXTENSION_VERSION})")

    info = doc.get("info") or {}
    metadata: Dict[str, Any] = {"name": info.get("title") or source_name or "imported", "version": str(info.get("version") or "0.0.0")}
    meta_ext = top.pop("metadata", {}) or {}
    if "description" in meta_ext:
        metadata["description"] = meta_ext["description"]
    elif info.get("description"):
        metadata["description"] = info["description"]
    if "author" in meta_ext:
        metadata["author"] = meta_ext["author"]
    elif (info.get("contact") or {}).get("name"):
        metadata["author"] = info["contact"]["name"]

    data: Dict[str, Any] = {"metadata": metadata}
    if "schema_version" in top:
        data["schema_version"] = top.pop("schema_version")
    serial = _serial(doc, top, report)
    top.pop("serial", None)
    if serial is not None:
        data["serial_config"] = serial
    if "framing" not in top:
        report.error(EXTENSION, "no framing: add x-omniuart.framing (type, header, length, command_id, integrity, ...)")
    else:
        data["framing"] = top.pop("framing")
    allowed = set(ProtocolSpec.model_fields) - _NATIVE_TOP - {"serial_config", "framing", "schema_version"}
    for key, value in top.items():
        if key in allowed:
            data[key] = value
        else:
            report.error(EXTENSION, f"unknown document attribute '{key}'")

    commands: List[Dict[str, Any]] = []
    telemetry: List[Dict[str, Any]] = []
    responses: List[Tuple[str, Dict[str, Any]]] = []
    for where, message, op in _messages(doc, resolve, report):
        ext = dict(message.get(EXTENSION) or {})
        kind = ext.pop("kind", None)
        if kind is None:
            if op is None:
                report.warn(where, f"message without {EXTENSION}.kind is not used by any operation; skipped")
                continue
            kind = "command" if op in ("publish", "send") else "telemetry"
            report.warn(where, f"no {EXTENSION}.kind, treated as {kind} ({op} operation)")
        name = ext.pop("name", None) or message.get("name") or message.get("title")
        if kind in ("command", "telemetry") and "description" not in ext and message.get("description"):
            ext["description"] = message["description"]
        if "id" not in ext and kind != "response":
            report.error(where, f"no {EXTENSION}.id: the message id on the wire is required")
            continue
        fields = _fields(message.get("payload"), f"{where}.payload", resolve, report)
        if kind == "command":
            commands.append({"name": name, **ext, "parameters": fields})
        elif kind == "telemetry":
            telemetry.append({"name": name, **ext, "fields": fields})
        elif kind == "response":
            command = ext.pop("command", None)
            if not command:
                report.error(where, f"response message has no {EXTENSION}.command naming the command it answers")
                continue
            responses.append((where, {"command": command, **ext, "fields": fields}))
        else:
            report.error(where, f"{EXTENSION}.kind must be command, response or telemetry, got '{kind}'")

    by_name = {c["name"]: c for c in commands}
    for where, resp in responses:
        command = resp.pop("command")
        if command not in by_name:
            report.error(where, f"response for unknown command '{command}'")
        elif "response" in by_name[command]:
            report.error(where, f"command '{command}' has more than one response message")
        else:
            by_name[command]["response"] = resp
    data["commands"] = commands
    data["telemetry"] = telemetry

    if report.errors:
        raise AsyncAPIImportError(report.errors, report)
    try:
        spec = ProtocolSpec.model_validate(data)
    except ValidationError as exc:
        errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        report.errors.extend(errors)
        raise AsyncAPIImportError(errors, report) from None
    return spec, report


def load_asyncapi_protocol(doc: Mapping[str, Any], source_name: Optional[str] = None) -> ProtocolSpec:
    """:func:`import_asyncapi` for loaders that need only the protocol; warnings are logged."""
    import logging

    spec, report = import_asyncapi(doc, source_name)
    log = logging.getLogger(__name__)
    for warning in report.warnings:
        log.warning("%s: %s", source_name or spec.metadata.name, warning)
    return spec
