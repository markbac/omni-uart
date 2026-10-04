import pytest
from omniuart.core.catalog import CatalogManager
from omniuart.visualizer import visualize_protocol, render_mermaid_diagram, render_svg_frame, render_html_visualizer

def test_protocol_visualizer_formats():
    catalog = CatalogManager()
    spec = catalog.get_protocol("binary_sensor_node.yaml")
    assert spec is not None

    # 1. Mermaid
    mermaid = visualize_protocol(spec, format="mermaid")
    assert "sequenceDiagram" in mermaid
    assert "ping" in mermaid

    # 2. SVG
    svg = visualize_protocol(spec, format="svg")
    assert "<svg" in svg
    assert "</svg>" in svg

    # 3. HTML
    html = visualize_protocol(spec, format="html")
    assert "<!DOCTYPE html>" in html
    assert "BinarySensorNode" in html
