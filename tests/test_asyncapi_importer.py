"""AsyncAPI documents with x-omniuart extensions as a protocol source (#346)."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List

import pytest
import yaml
from jsonschema import Draft202012Validator

from omniuart.core.asyncapi_exporter import EXTENSION, export_asyncapi_dict, export_asyncapi_json, export_asyncapi_yaml
from omniuart.core.asyncapi_importer import AsyncAPIImportError, import_asyncapi
from omniuart.core.catalog import CatalogManager
from omniuart.core.models import ProtocolSpec, load_protocol, load_protocol_text
from omniuart.schema_export import build_asyncapi_extension_schema, default_schema_dir, render


def _bundled() -> List[str]:
    logging.disable(logging.WARNING)
    try:
        return [p.name for p in CatalogManager().list_protocol_files()]
    finally:
        logging.disable(logging.NOTSET)


BUNDLED = _bundled()


def _spec(name: str) -> ProtocolSpec:
    logging.disable(logging.WARNING)
    try:
        spec = CatalogManager().get_protocol(name)
    finally:
        logging.disable(logging.NOTSET)
    assert spec is not None
    return spec


def _documents(spec: ProtocolSpec) -> Iterator[Dict[str, Any]]:
    yield export_asyncapi_dict(spec)
    yield yaml.safe_load(export_asyncapi_yaml(spec))
    yield json.loads(export_asyncapi_json(spec))


# ------------------------------------------------------------------------------------------- round trip


def test_at_least_three_bundled_protocols_are_covered() -> None:
    assert len(BUNDLED) >= 3
    for required in ("binary_sensor_node.yaml", "ascii_device.yaml", "custom_crc_device.yaml", "modbus-rtu-uart-interface.json"):
        assert required in BUNDLED


@pytest.mark.parametrize("name", BUNDLED)
def test_export_then_import_yields_an_equal_protocol(name: str) -> None:
    spec = _spec(name)
    for doc in _documents(spec):  # as a dict, and through YAML and JSON text
        imported, report = import_asyncapi(doc)
        assert imported == spec
        assert report.warnings == [] and report.errors == []


def test_the_exporter_writes_the_extensions() -> None:
    spec = _spec("binary_sensor_node.yaml")
    doc = export_asyncapi_dict(spec)
    top = doc[EXTENSION]
    assert top["version"] == "1.0" and top["framing"]["type"] == "binary" and top["serial"]["baudrate"] == 115200
    assert top["framing"]["integrity"]["algorithm"] == "crc16_modbus"
    request = doc["channels"]["omniuart/cmd/ping"]["publish"]["message"]
    assert request[EXTENSION] == {"kind": "command", "name": "ping", "id": 1, "safety": "read_only", "tags": ["dashboard"]}
    response = doc["channels"]["omniuart/resp/ping"]["subscribe"]["message"]
    assert response[EXTENSION]["kind"] == "response" and response[EXTENSION]["command"] == "ping" and response[EXTENSION]["id"] == 0x81
    schema = doc["components"]["schemas"]["get_readings_Request"]["properties"]
    assert schema["command_id"][EXTENSION] == {"role": "command_id"}
    assert schema["channel"][EXTENSION]["type"] == "uint8"


def test_exported_extensions_validate_against_the_extension_schema() -> None:
    schema = build_asyncapi_extension_schema()
    Draft202012Validator.check_schema(schema)
    defs = schema["$defs"]

    def validator(name: str) -> Draft202012Validator:
        return Draft202012Validator({"$ref": f"#/$defs/{name}", "$defs": defs})

    for name in ("binary_sensor_node.yaml", "smart_actuator.json", "modbus-rtu-uart-interface.json", "ascii_device.yaml"):
        doc = json.loads(export_asyncapi_json(_spec(name)))
        assert not list(validator("document").iter_errors(doc[EXTENSION]))
        for channel in doc["channels"].values():
            for op in channel.values():
                assert not list(validator("message").iter_errors(op["message"][EXTENSION]))
        for component in doc["components"]["schemas"].values():
            for prop in component["properties"].values():
                errors = list(validator("field").iter_errors(prop[EXTENSION]))
                assert not errors, [e.message for e in errors]


def test_committed_extension_schema_matches_the_models() -> None:
    committed = (default_schema_dir() / "x-omniuart.schema.json").read_text(encoding="utf-8")
    assert committed == render(build_asyncapi_extension_schema()), "run: python -m omniuart.schema_export"


# --------------------------------------------------------------------------------------------- discovery


def test_catalog_discovers_an_asyncapi_file(tmp_path: Path) -> None:
    spec = _spec("custom_crc_device.yaml")
    (tmp_path / "custom-crc.asyncapi.yaml").write_text(export_asyncapi_yaml(spec), encoding="utf-8")
    catalog = CatalogManager(protocol_dirs=[tmp_path])
    assert catalog.get_protocol("custom-crc.asyncapi") == spec
    assert catalog.get_protocol(spec.metadata.name) == spec
    assert load_protocol(tmp_path / "custom-crc.asyncapi.yaml") == spec
    assert load_protocol_text(export_asyncapi_json(spec)) == spec


def test_an_imported_protocol_drives_the_simulated_device() -> None:
    from omniuart.core.session import SerialSession
    from omniuart.core.transport import VirtualTransport

    spec, _ = import_asyncapi(export_asyncapi_dict(_spec("binary_sensor_node.yaml")))

    async def go() -> Any:
        async with SerialSession(spec, VirtualTransport(spec, latency_ms=0, jitter_ms=0)) as session:
            return await session.send("get_readings", {"channel": 1})

    assert asyncio.run(go()).ok


# --------------------------------------------------------------------------------------- hand-written docs

HAND_WRITTEN_V3 = {
    "asyncapi": "3.0.0",
    "info": {"title": "Thermostat", "version": "2.1.0", "description": "Hand-written AsyncAPI 3 source"},
    EXTENSION: {
        "serial": {"baudrate": 9600},
        "framing": {
            "type": "binary",
            "header": [0xAA],
            "length": {"type": "uint8", "includes": "payload_only"},
            "command_id": {"type": "uint8"},
            "integrity": {"algorithm": "sum8"},
        },
        "error_replies": [{"id": 0x7F, "name": "NAK"}],
    },
    "channels": {
        "setpoint": {
            "address": "thermostat/setpoint",
            "messages": {
                "set": {"$ref": "#/components/messages/SetSetpoint"},
                "ack": {"$ref": "#/components/messages/SetpointAck"},
            },
        },
        "status": {"address": "thermostat/status", "messages": {"status": {"$ref": "#/components/messages/Status"}}},
    },
    "operations": {
        "sendSetpoint": {"action": "send", "channel": {"$ref": "#/channels/setpoint"}},
        "receiveStatus": {"action": "receive", "channel": {"$ref": "#/channels/status"}},
    },
    "components": {
        "messages": {
            "SetSetpoint": {
                "name": "set_setpoint",
                "description": "Set the target temperature",
                EXTENSION: {"kind": "command", "id": 0x10, "safety": "idempotent"},
                "payload": {"type": "object", "properties": {
                    "celsius": {"type": "number", "minimum": 5, "maximum": 30, EXTENSION: {"type": "int16", "endian": "big", "scale": 0.1}},
                }},
            },
            "SetpointAck": {
                EXTENSION: {"kind": "response", "command": "set_setpoint", "id": 0x90},
                "payload": {"type": "object", "properties": {"accepted": {"type": "boolean"}}},
            },
            "Status": {
                "name": "status",
                EXTENSION: {"kind": "telemetry", "id": 0x20},
                "payload": {"$ref": "#/components/schemas/Status"},
            },
        },
        "schemas": {
            "Status": {"type": "object", "properties": {
                "temperature": {"type": "integer", EXTENSION: {"type": "int16", "scale": 0.1, "unit": "°C"}},
                "mode": {"type": "integer", EXTENSION: {"type": "enum", "options": [{"value": 0, "label": "off"}, {"value": 1, "label": "heat"}]}},
            }},
        },
    },
}


def test_a_hand_written_asyncapi_3_document_imports() -> None:
    spec, report = import_asyncapi(copy.deepcopy(HAND_WRITTEN_V3))
    assert spec.metadata.name == "Thermostat" and spec.metadata.version == "2.1.0"
    cmd = spec.get_command("set_setpoint")
    assert cmd is not None and cmd.id == 0x10 and cmd.description == "Set the target temperature"
    assert cmd.parameters[0].type.value == "int16" and cmd.parameters[0].endian == "big"
    assert cmd.parameters[0].min == 5 and cmd.parameters[0].max == 30  # from the JSON Schema keywords
    assert cmd.response is not None and cmd.response.id == 0x90 and cmd.response.fields[0].type.value == "bool"
    assert spec.telemetry[0].fields[1].options == {0: "off", 1: "heat"}
    assert spec.error_replies[0].name == "NAK"
    assert any("assumed 'bool'" in w for w in report.warnings)  # nothing approximated silently


def test_every_problem_is_reported_instead_of_dropped() -> None:
    doc = copy.deepcopy(HAND_WRITTEN_V3)
    del doc[EXTENSION]["framing"]
    doc[EXTENSION]["checksum"] = "crc"
    messages = doc["components"]["messages"]
    del messages["SetSetpoint"][EXTENSION]["id"]
    messages["SetpointAck"][EXTENSION]["command"] = "nope"
    doc["components"]["schemas"]["Status"]["properties"]["temperature"] = {"type": "integer"}
    doc["components"]["schemas"]["Status"]["properties"]["mode"][EXTENSION]["colour"] = "red"
    with pytest.raises(AsyncAPIImportError) as caught:
        import_asyncapi(doc)
    errors = "\n".join(caught.value.errors)
    for expected in (
        "no framing",
        "unknown document attribute 'checksum'",
        "no x-omniuart.id",
        "response for unknown command 'nope'",
        "temperature: no x-omniuart.type",
        "unknown x-omniuart field attribute 'colour'",
    ):
        assert expected in errors, expected


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d.update(asyncapi="1.2.0"), "version 1.2.0 is not supported"),
        (lambda d: d[EXTENSION].update(version="2.0"), "extension version 2.0 is not supported"),
        (lambda d: d["components"]["messages"]["Status"].update(payload={"$ref": "other.yaml#/Status"}), "only local $ref"),
        (lambda d: d["components"]["messages"]["Status"].update(payload={"$ref": "#/components/schemas/Missing"}), "does not resolve"),
        (lambda d: d["components"]["messages"]["Status"][EXTENSION].update(kind="event"), "must be command, response or telemetry"),
        (lambda d: d[EXTENSION].pop("serial"), "no serial settings"),
        (lambda d: d[EXTENSION]["framing"].update(type="morse"), "framing.type"),
    ],
)
def test_import_errors_name_the_problem(mutate: Any, message: str) -> None:
    doc = copy.deepcopy(HAND_WRITTEN_V3)
    mutate(doc)
    with pytest.raises(AsyncAPIImportError, match=None) as caught:
        import_asyncapi(doc)
    assert any(message in e for e in caught.value.errors), caught.value.errors


def test_a_message_without_kind_is_typed_from_its_operation_with_a_warning() -> None:
    doc = export_asyncapi_dict(_spec("binary_sensor_node.yaml"))
    del doc["channels"]["omniuart/telemetry/periodic_status"]["subscribe"]["message"][EXTENSION]["kind"]
    spec, report = import_asyncapi(doc)
    assert [t.name for t in spec.telemetry] == ["periodic_status"]
    assert any("treated as telemetry (subscribe operation)" in w for w in report.warnings)


def test_a_non_asyncapi_document_is_refused() -> None:
    with pytest.raises(AsyncAPIImportError, match="not an AsyncAPI document"):
        import_asyncapi({"openapi": "3.1.0"})


# ---------------------------------------------------------------------------------------------------- CLI


def test_cli_imports_an_asyncapi_document(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from omniuart.cli import main

    spec = _spec("smart_actuator.json")
    source = tmp_path / "actuator.asyncapi.yaml"
    source.write_text(export_asyncapi_yaml(spec), encoding="utf-8")
    for suffix in (".yaml", ".json"):
        out = tmp_path / f"actuator{suffix}"
        assert main(["--log-level", "ERROR", "import", "asyncapi", str(source), "-o", str(out)]) == 0
        assert load_protocol(out) == spec
    assert "Imported protocol" in capsys.readouterr().out

    broken = tmp_path / "broken.yaml"
    doc = copy.deepcopy(HAND_WRITTEN_V3)
    del doc[EXTENSION]["framing"]
    broken.write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert main(["--log-level", "ERROR", "import", "asyncapi", str(broken)]) == 2
    assert "no framing" in capsys.readouterr().err
    assert main(["--log-level", "ERROR", "import", "pdf", str(broken)]) == 2


def test_cli_import_still_accepts_a_bare_csv_file(tmp_path: Path) -> None:
    from omniuart.cli import main
    from omniuart.importers_exporters import export_csv_protocol

    csv_file = tmp_path / "p.csv"
    csv_file.write_text(export_csv_protocol(_spec("binary_sensor_node.yaml")), encoding="utf-8")
    assert main(["--log-level", "ERROR", "import", str(csv_file)]) == 0
    assert main(["--log-level", "ERROR", "import", "csv", str(csv_file)]) == 0
