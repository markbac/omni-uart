from omniuart.core.catalog import CatalogManager
from omniuart.visualizer import visualize_protocol, render_svg_frame, render_html_visualizer
from omniuart.core.models import ProtocolSpec, ProtocolMeta, SerialConfig, FramingConfig, FramingType, CommandSpec


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
    assert "Header" in svg
    assert "Length" in svg
    assert "CRC" in svg
    assert "[0.." in svg or "[0]" in svg

    # 3. HTML - check CDN URL is fixed and pinned (#330)
    html_out = visualize_protocol(spec, format="html")
    assert "<!DOCTYPE html>" in html_out
    assert "BinarySensorNode" in html_out
    assert "mermaid.min.min.js" not in html_out
    assert "mermaid@10.9.1/dist/mermaid.min.js" in html_out
    assert "Sample Encoded Frame" in html_out


def test_visualizer_html_escaping():
    """Ensure protocol metadata and command names with special characters are safely escaped (#330, #316)."""
    spec = ProtocolSpec(
        schema_version="1.0.0",
        metadata=ProtocolMeta(name="<EvilCorp & Co>", version="1.0\"beta"),
        serial_config=SerialConfig(baudrate=115200),
        framing=FramingConfig(type=FramingType.BINARY, header=[0xAA]),
        commands=[CommandSpec(name="exploit<script>", id=1)]
    )

    svg = render_svg_frame(spec)
    assert "<script>" not in svg
    assert "&lt;EvilCorp &amp; Co&gt;" in svg
    assert "exploit&lt;script&gt;" in svg

    html_page = render_html_visualizer(spec)
    assert "<script>exploit" not in html_page
    assert "&lt;EvilCorp &amp; Co&gt;" in html_page
