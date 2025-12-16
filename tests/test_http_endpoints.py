"""Test HTTP endpoint functionality."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.server.http import create_app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    app = create_app()
    return TestClient(app)


def test_health_endpoint_no_auth(client):
    """Test that /health endpoint works without authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_no_auth_no_token_env(client):
    """Test that /ready endpoint works without auth when no token is set."""
    with patch.dict(os.environ, {}, clear=True):
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_ready_endpoint_no_auth_with_token_env(client):
    """Test that /ready endpoint works without auth even when token is set."""
    with patch.dict(os.environ, {"DOMAIN_MCP_HTTP_TOKEN": "test-token"}):
        # Create new app with token environment
        app = create_app()
        test_client = TestClient(app)

        # Should work without auth (this is the fix we implemented)
        response = test_client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_protected_endpoint_requires_auth(client):
    """Test that protected endpoints still require authentication."""
    with patch.dict(os.environ, {"DOMAIN_MCP_HTTP_TOKEN": "test-token"}):
        # Create new app with token environment
        app = create_app()
        test_client = TestClient(app)

        # Should require auth for protected endpoints
        response = test_client.post(
            "/tools/get_key_metrics_raw",
            json={"dataset_types": ["boot-time-verbose"], "data": []},
        )
        assert response.status_code == 401  # Unauthorized

        # Should work with proper auth and valid data
        response = test_client.post(
            "/tools/get_key_metrics_raw",
            headers={"Authorization": "Bearer test-token"},
            json={
                "dataset_types": ["boot-time-verbose"],
                "data": [
                    {
                        "boot_metrics": {
                            "total_boot_time_ms": 12500,
                            "status": {"success": True},
                        },
                        "system_info": {"os_id": "rhel-9.2", "mode": "standard"},
                        "timestamp": "2025-09-22T10:30:00Z",
                    }
                ],
            },
        )
        assert response.status_code == 200
