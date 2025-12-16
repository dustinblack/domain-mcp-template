"""Tests for HTTP server memory observability features.

These tests verify that memory observability doesn't break the server
and gracefully handles different environments.
"""

from unittest.mock import patch

import pytest


def test_memory_observability_does_not_break_server():
    """Integration test: verify memory observability doesn't break server startup."""
    from fastapi.testclient import TestClient

    from src.server.http import create_app

    # Start server with real psutil (no mocks)
    app = create_app()
    client = TestClient(app)

    # Verify health endpoint works
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify ready endpoint works
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_psutil_unavailable_graceful_handling():
    """Test that server starts even without psutil."""
    from fastapi.testclient import TestClient

    from src.server.http import create_app

    # Mock psutil as unavailable
    with patch("src.server.http.psutil", side_effect=ImportError("psutil not found")):
        app = create_app()
        client = TestClient(app)

        # Server should still work
        response = client.get("/health")
        assert response.status_code == 200


def test_cgroup_files_not_found_graceful_handling():
    """Test that server handles missing cgroup files gracefully."""
    from fastapi.testclient import TestClient

    from src.server.http import create_app

    # Mock open to always raise FileNotFoundError for cgroup paths
    original_open = open

    def mock_open_selective(path, *args, **kwargs):
        if "/sys/fs/cgroup" in str(path):
            raise FileNotFoundError("cgroup not available")
        return original_open(path, *args, **kwargs)

    with patch("builtins.open", side_effect=mock_open_selective):
        app = create_app()
        client = TestClient(app)

        # Server should still work without cgroup info
        response = client.get("/ready")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
