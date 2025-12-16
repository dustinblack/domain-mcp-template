"""Tests for startup guidance and capabilities log emission."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.server.http import create_app


def _find_record(caplog, name: str):
    """Return first log record with matching message name, if present."""
    for rec in caplog.records:
        if rec.getMessage() == name:
            return rec
    return None


def test_guidance_logged_when_config_missing(caplog):
    """When no config is set, guidance log should be emitted with hints."""
    caplog.set_level("INFO")
    with patch.dict("os.environ", {}, clear=True):
        c = TestClient(create_app())
        assert c.get("/health").status_code == 200
    rec = _find_record(caplog, "http.startup.guidance")
    assert rec is not None
    assert getattr(rec, "problem") == "config_not_found"
    assert getattr(rec, "raw_mode_hint") is True


def test_capabilities_log_emitted(caplog):
    """Capabilities snapshot should be logged at startup."""
    caplog.set_level("INFO")
    with patch.dict("os.environ", {}, clear=True):
        c = TestClient(create_app())
        assert c.get("/health").status_code == 200
    rec = _find_record(caplog, "http.startup.capabilities")
    assert rec is not None
    assert isinstance(getattr(rec, "tools"), list)
    assert isinstance(getattr(rec, "plugins"), list)
