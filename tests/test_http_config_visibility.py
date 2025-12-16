"""Functional tests for HTTP startup configuration visibility logging.

These tests assert that `create_app()` logs a structured startup record with
configuration discovery details and adapter initialization summary.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.server.http import create_app


def _find_settings_record(caplog) -> object | None:
    """Return the first log record matching the startup settings marker."""
    for rec in caplog.records:
        if rec.getMessage() == "http.startup.settings":
            return rec
    return None


def test_startup_logs_config_not_found(caplog):
    """Logs should indicate when DOMAIN_MCP_CONFIG is not found."""
    caplog.set_level("INFO")
    missing_path = "/tmp/does-not-exist-config.json"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DOMAIN_MCP_CONFIG", missing_path)
        app = create_app()
        assert app is not None

    rec = _find_settings_record(caplog)
    assert rec is not None
    assert getattr(rec, "config_path") == missing_path
    assert getattr(rec, "config_found") is False
    # No adapters initialized when config is missing
    assert getattr(rec, "adapters_initialized") == []


def test_startup_logs_config_loaded_adapters_init(tmp_path: Path, caplog):
    """Logs should reflect successful config parse and adapter initialization."""
    caplog.set_level("INFO")
    cfg_path = tmp_path / "app-config.json"
    cfg = {
        "sources": {
            "horreum_http": {
                "endpoint": "http://example",
                "api_key": None,
                "type": "http",
                "timeout_seconds": 5,
            }
        },
        "enabled_plugins": {},
    }
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DOMAIN_MCP_CONFIG", str(cfg_path))
        app = create_app()
        assert app is not None

    rec = _find_settings_record(caplog)
    assert rec is not None
    assert getattr(rec, "config_path") == str(cfg_path)
    assert getattr(rec, "config_found") is True
    assert getattr(rec, "config_error") in (None, "")
    adapters = getattr(rec, "adapters_initialized")
    assert isinstance(adapters, list)
    assert any(item.startswith("horreum_http:") for item in adapters)
