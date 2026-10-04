import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.importers_exporters import export_csv_protocol, import_csv_protocol

def test_csv_import_export_round_trip():
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node.yaml")
    assert spec is not None

    csv_text = export_csv_protocol(spec)
    assert "protocol_name" in csv_text
    assert "ping" in csv_text

    imported_spec, losses = import_csv_protocol(csv_text)
    assert imported_spec.metadata.name == spec.metadata.name
    assert len(imported_spec.commands) == len(spec.commands)
