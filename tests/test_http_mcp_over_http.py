"""Tests for MCP-over-HTTP endpoints (/mcp SSE and /mcp/http).

The Domain MCP server supports dual transport:
- SSE transport at /mcp (for Gemini CLI)
- HTTP JSON-RPC transport at /mcp/http (for Claude Desktop, curl)
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.server.http import create_app


def _build_client() -> TestClient:
    """Create a FastAPI TestClient from the application factory."""
    app = create_app()
    return TestClient(app)


def test_mcp_transports_mounted():
    """Both SSE and HTTP transports should be mounted and accessible.

    Note: fastapi-mcp mounts /mcp and /mcp/http dynamically, so they won't appear
    in the OpenAPI schema. We verify endpoints exist by checking they don't 404.

    We test POST to /mcp which should return 405 (Method Not Allowed) since SSE
    uses GET. This proves the endpoint exists without triggering SSE streaming.
    """
    c = _build_client()

    # POST to /mcp should return 405 (not 404) proving SSE endpoint exists
    # The custom conflicting endpoint has been removed, so this should be 405
    r = c.post("/mcp", json={})
    assert r.status_code == 405, (
        f"/mcp should exist (405 for POST), got {r.status_code}. "
        f"404=missing, 401=old auth"
    )


def test_rest_endpoints_still_work():
    """Regular REST tool endpoints should still work alongside MCP transports."""
    c = _build_client()
    # Test the REST endpoint for get_key_metrics_raw
    r = c.post(
        "/tools/get_key_metrics_raw",
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
    assert r.status_code == 200
    body = r.json()
    assert "metric_points" in body
