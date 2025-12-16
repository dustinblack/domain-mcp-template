"""Functional tests for container-oriented startup diagnostics logging."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.server.http import create_app


def _find_container_record(caplog):
    """Return the startup container diagnostics log record if present."""
    for rec in caplog.records:
        if rec.getMessage() == "http.startup.container":
            return rec
    return None


def _find_container_status_record(caplog):
    for rec in caplog.records:
        if rec.getMessage() == "http.startup.container_status":
            return rec
    return None


def test_container_diagnostics_logged(caplog, tmp_path):
    """Container diagnostics should log env visibility and mount presence."""
    caplog.set_level("INFO")
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text('{\n  "sources": {}, "enabled_plugins": {}\n}\n')
    with patch.dict(
        "os.environ",
        {"DOMAIN_MCP_HTTP_TOKEN": "t", "DOMAIN_MCP_CONFIG": str(cfg_path)},
    ):
        app = create_app()
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200

    rec = _find_container_record(caplog)
    assert rec is not None
    assert getattr(rec, "env_has_token") is True
    assert getattr(rec, "env_has_config") is True
    assert getattr(rec, "config_mount_exists") is True
    assert isinstance(getattr(rec, "workdir"), str)

    # And container_status summary should be present
    srec = _find_container_status_record(caplog)
    assert srec is not None
    assert isinstance(getattr(srec, "configured"), bool)
    assert isinstance(getattr(srec, "raw_mode_available"), bool)
