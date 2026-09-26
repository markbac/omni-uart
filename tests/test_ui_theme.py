"""Tests for Web UI Theme Toggle & Compact Mode rendering."""

from __future__ import annotations

from fastapi.testclient import TestClient
from omniuart.ui.app import app

client = TestClient(app)


def test_ui_index_contains_theme_and_compact_controls() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "light-theme" in response.text
    assert "compact-mode" in response.text
    assert "🌓 Theme" in response.text
    assert "↕️ Compact" in response.text
