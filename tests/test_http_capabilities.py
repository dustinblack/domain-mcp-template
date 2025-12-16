"""Functional tests for /capabilities endpoint."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.adapters import reset_adapters
from src.server.http import create_app


def test_capabilities_basic_no_sources():
    """Capabilities should show raw mode only when no sources configured."""
    with patch.dict("os.environ", {}, clear=True):
        reset_adapters()
        app = create_app()
        c = TestClient(app)
        r = c.get("/capabilities")
        assert r.status_code == 200
        body = r.json()
        assert body["http_auth"] == "disabled"
        assert body["modes"]["raw"] is True
        assert body["modes"]["source_driven"] is False
        assert "get_key_metrics_raw" in body["tools"]
        assert isinstance(body["plugins"], list) and len(body["plugins"]) >= 1


def test_capabilities_with_token_and_sources(tmp_path):
    """Capabilities should reflect auth enabled and list configured sources."""
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(
        (
            "{"
            '"sources": {"s1": {"endpoint": "http://example",'
            '"type": "http","timeout_seconds": 1}}, '
            '"enabled_plugins": {}}'
        )
    )
    with patch.dict(
        "os.environ",
        {"DOMAIN_MCP_HTTP_TOKEN": "t", "DOMAIN_MCP_CONFIG": str(cfg_path)},
    ):
        app = create_app()
        c = TestClient(app)
        r = c.get("/capabilities")
        assert r.status_code == 200
        body = r.json()
        assert body["http_auth"] == "enabled"
        assert body["modes"]["source_driven"] is True
        assert "s1" in body["sources"]
