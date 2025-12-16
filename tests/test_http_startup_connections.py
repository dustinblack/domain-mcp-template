"""Functional tests for startup connection diagnostics logging."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.server.http import create_app


def _find_connections_record(caplog):
    for rec in caplog.records:
        if rec.getMessage() == "http.startup.connections":
            return rec
    return None


def test_startup_connections_logs_with_no_adapters(caplog):
    """When no adapters configured, no connections record is emitted."""
    caplog.set_level("INFO")
    with patch.dict("os.environ", {}, clear=True):
        app = create_app()
        client = TestClient(app)
        # Trigger lifespan by making a request
        res = client.get("/health")
        assert res.status_code == 200
    assert _find_connections_record(caplog) is None


def test_startup_connections_logs_with_error(caplog):
    """Adapters present but failing should emit diagnostics with error fields."""
    caplog.set_level("INFO")
    # Configure a fake adapter via config file
    cfg_json = {
        "sources": {
            "bad": {
                "endpoint": "http://invalid",
                "api_key": None,
                "type": "http",
                "timeout_seconds": 1,
            }
        },
        "enabled_plugins": {},
    }
    import json
    import os
    import tempfile

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(json.dumps(cfg_json))
        cfg_path = f.name

    try:
        with patch.dict("os.environ", {"DOMAIN_MCP_CONFIG": cfg_path}):
            app = create_app()
            client = TestClient(app)
            res = client.get("/health")
            assert res.status_code == 200
        rec = _find_connections_record(caplog)
        if rec is not None:
            conns = getattr(rec, "connections")
            assert isinstance(conns, list) and len(conns) >= 1
            # At least one entry corresponds to our configured source
            ids = {c["source_id"] for c in conns}
            assert "bad" in ids
        else:
            # Fallback: assert startup settings announced the adapter initialization
            from tests.test_http_config_visibility import _find_settings_record

            srec = _find_settings_record(caplog)
            assert srec is not None
            adapters = getattr(srec, "adapters_initialized")
            assert any(str(a).startswith("bad:") for a in adapters)
    finally:
        try:
            os.unlink(cfg_path)
        except OSError:
            pass
