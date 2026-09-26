"""Unit tests for AsyncAPI 2.6.0 specification exporter."""

from __future__ import annotations

import yaml
from omniuart.core.catalog import CatalogManager
from omniuart.core.asyncapi_exporter import export_asyncapi_dict, export_asyncapi_yaml, export_asyncapi_json


def test_asyncapi_exporter_structure() -> None:
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node")
    assert spec is not None

    doc = export_asyncapi_dict(spec)
    assert doc["asyncapi"] == "2.6.0"
    assert doc["info"]["title"] == spec.metadata.name
    assert "channels" in doc
    assert "servers" in doc
    assert "components" in doc

    yaml_str = export_asyncapi_yaml(spec)
    parsed = yaml.safe_load(yaml_str)
    assert parsed["asyncapi"] == "2.6.0"

    json_str = export_asyncapi_json(spec)
    assert '"asyncapi": "2.6.0"' in json_str
