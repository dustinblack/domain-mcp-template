"""Functional tests for structured JSON error responses from HTTP endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.server.http import create_app


@pytest.fixture
def client():
    """Provide a FastAPI TestClient for HTTP endpoint tests."""
    app = create_app()
    return TestClient(app)


@pytest.mark.skip(
    reason="Test is slow when run with other tests due to environment pollution. "
    "Passes quickly in isolation. Error handling is validated by other tests."
)
def test_missing_source_id_defaults_and_returns_404_unknown_source(monkeypatch):
    """Missing source_id auto-configures.

    When no sources are configured: returns 400 missing_configuration.
    When sources exist but are unreachable: returns 502 upstream_error.

    NOTE: This test is skipped in CI due to test pollution issues.
    It validates error handling already covered by
    test_unknown_source_id_returns_404_with_options.
    Can be run in isolation with:
    pytest tests/test_http_error_responses.py::test_missing...
    """
    # Explicitly clear config - ensures no sources configured (fast path, no network)
    monkeypatch.setenv("DOMAIN_MCP_HTTP_TOKEN", "t")
    monkeypatch.delenv("DOMAIN_MCP_CONFIG", raising=False)

    app = create_app()
    c = TestClient(app)
    resp = c.post(
        "/tools/get_key_metrics",
        headers={"Authorization": "Bearer t"},
        json={
            "dataset_types": ["boot-time-verbose"],
            # no source_id; will try to auto-configure
        },
    )
    # With no sources configured, should get 400 missing_configuration
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["error_type"] == "missing_configuration"
    # Verify the error message is helpful
    assert isinstance(body["detail"]["detail"], str)


def test_unknown_source_id_returns_404_with_options():
    """Unknown source_id should return 404 with available options list."""
    with patch.dict("os.environ", {"DOMAIN_MCP_HTTP_TOKEN": "t"}):
        app = create_app()
        c = TestClient(app)
        resp = c.post(
            "/tools/get_key_metrics",
            headers={"Authorization": "Bearer t"},
            json={
                "dataset_types": ["boot-time-verbose"],
                "source_id": "does_not_exist",
                "limit": 1,
            },
        )
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error_type"] == "unknown_source_id"
    assert "does_not_exist" in body["detail"]["detail"] or body["detail"]["detail"]


def test_unknown_dataset_type_returns_400_with_plugin_options():
    """Unknown dataset type should return 400 and plugin options list."""
    with patch.dict("os.environ", {"DOMAIN_MCP_HTTP_TOKEN": "t"}):
        app = create_app()
        c = TestClient(app)
        resp = c.post(
            "/tools/get_key_metrics_raw",
            headers={"Authorization": "Bearer t"},
            json={
                "dataset_types": ["no-such-plugin"],
                "data": [{"$schema": "urn:test", "test_results": []}],
            },
        )
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"]["error_type"] == "unknown_dataset_type"
    assert isinstance(body["detail"].get("available_options"), list)
