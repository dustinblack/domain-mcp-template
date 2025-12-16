"""Connectivity test for the Horreum MCP container/server.

This test is opt-in and will only run when the environment variable
`HORREUM_MCP_URL` is provided. Optionally supports `HORREUM_TOKEN` for auth.

Run locally via the container e2e script or manually by exporting:

- `HORREUM_MCP_URL=http://127.0.0.1:3001`
- `HORREUM_TOKEN=...` (optional)
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("HORREUM_MCP_URL"),
    reason="Skipped unless HORREUM_MCP_URL is set",
)


def test_horreum_mcp_health_connectivity() -> None:
    """Verify Horreum MCP responds to /health."""

    horreum_url = os.environ["HORREUM_MCP_URL"]
    token = os.environ.get("HORREUM_TOKEN")

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=5.0) as client:
        resp = client.get(f"{horreum_url}/health", headers=headers)
        assert resp.status_code == 200, resp.text
