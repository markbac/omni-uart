"""Unit test suite for Web UI hierarchical tag tree and discriminator badge endpoints."""

from fastapi.testclient import TestClient
from omniuart.ui.app import app

client = TestClient(app)


def test_ui_protocols_list():
    response = client.get("/api/protocols")
    assert response.status_code == 200
    data = response.json()
    assert "protocols" in data
    assert len(data["protocols"]) > 0


def test_ui_protocol_tag_hierarchy():
    response = client.get("/api/protocol/ubx-uart-interface.json")
    assert response.status_code == 200
    data = response.json()
    assert "spec" in data
    assert "tags" in data
    assert "tag_groups" in data
    assert "gnss/nav" in data["tags"] or "gnss/config" in data["tags"]


def test_ui_index_html_renders_tree():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "tagTreeMenu" in html
    assert "renderTagTree" in html
    assert "getDiscriminatorBadge" in html
    assert "badge-disc" in html
