"""Container-oriented tests for configuration error visibility."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.server.http import create_app


def _find_record(caplog, name: str):
    for rec in caplog.records:
        if rec.getMessage() == name:
            return rec
    return None


def test_missing_config_guidance_logged_container(caplog):
    """Guidance log should appear when no DOMAIN_MCP_CONFIG is provided."""
    caplog.set_level("INFO")
    with patch.dict("os.environ", {}, clear=True):
        c = TestClient(create_app())
        assert c.get("/health").status_code == 200
    rec = _find_record(caplog, "http.startup.guidance")
    assert rec is not None
    assert getattr(rec, "problem") == "config_not_found"
