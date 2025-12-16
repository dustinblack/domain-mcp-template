"""Scaffold for container-to-container connectivity test (manual enable).

This test is skipped by default in CI. To run locally or in a pipeline that
provisions containers, set `ENABLE_CONTAINER_E2E=1` and provide:

- `DOMAIN_MCP_URL` (e.g., http://localhost:8080)
- `HORREUM_MCP_URL` (optional; if provided, we probe it)
- `DOMAIN_MCP_TOKEN` (optional; Bearer token if auth enabled)

The test verifies basic liveness of both services and documents where to add a
full end-to-end call (e.g., posting to /tools/get_key_metrics with source_id).
"""

from __future__ import annotations

import os

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("ENABLE_CONTAINER_E2E") != "1",
    reason="Skipped unless ENABLE_CONTAINER_E2E=1 is set",
)


def test_container_services_reachable():
    """Check that Domain MCP (and optionally Horreum MCP) respond to /health."""

    domain_url = os.environ.get("DOMAIN_MCP_URL")
    horreum_url = os.environ.get("HORREUM_MCP_URL")
    token = os.environ.get("DOMAIN_MCP_TOKEN")
    assert domain_url, "DOMAIN_MCP_URL is required when ENABLE_CONTAINER_E2E=1"

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=5.0) as client:
        # Domain MCP health
        r = client.get(f"{domain_url}/health", headers=headers)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

        # Optionally, check Horreum MCP health if provided
        if horreum_url:
            rh = client.get(f"{horreum_url}/health")
            assert rh.status_code == 200

    # Optional end-to-end source-driven call when env vars are provided
    source_id = os.environ.get("E2E_SOURCE_ID")
    test_id = os.environ.get("E2E_TEST_ID")
    limit = os.environ.get("E2E_LIMIT")
    dataset_types = os.environ.get("E2E_DATASET_TYPES", "boot-time-verbose")
    schema_uri = os.environ.get("E2E_SCHEMA_URI")
    if source_id and test_id and limit:
        payload = {
            "dataset_types": [d.strip() for d in dataset_types.split(",") if d],
            "source_id": source_id,
            "test_id": test_id,
            "limit": int(limit),
        }
        if schema_uri:
            payload["schema_uri"] = schema_uri
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{domain_url}/tools/get_key_metrics",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert isinstance(body.get("metric_points"), list)
