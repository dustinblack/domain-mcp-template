"""Env-gated integration smoke tests against a live Horreum MCP.

These tests are skipped unless the required environment variables are set:

- HORREUM_BASE_URL: Base URL of the Horreum MCP HTTP API
- HORREUM_API_KEY:  Bearer token for the Horreum MCP (may be empty if not required)

Optional variables to exercise deeper paths:

- HORREUM_TEST_ID:   A test identifier to query runs/datasets
- HORREUM_SCHEMA_URI: Optional schema filter for datasets.search

The goal is to validate that basic contract calls work end-to-end. The test
uses small page sizes to minimize load and runtime.
"""

from __future__ import annotations

import os
from typing import Optional

import pytest

from src.adapters.horreum import HorreumAdapter
from src.schemas.source_mcp_contract import (
    DatasetsGetRequest,
    DatasetsSearchRequest,
    RunsListRequest,
    SourceDescribeRequest,
)


def _get_env(name: str) -> Optional[str]:
    val = os.environ.get(name)
    return val if val and val.strip() else None


@pytest.mark.asyncio
async def test_horreum_source_describe_env_gated() -> None:
    """Validate source.describe against a live Horreum MCP (if configured)."""
    base_url = _get_env("HORREUM_BASE_URL")
    api_key = os.environ.get("HORREUM_API_KEY", "")

    if not base_url:
        pytest.skip("HORREUM_BASE_URL not set; skipping live integration smoke")

    adapter = HorreumAdapter(base_url, api_key, timeout=10)
    resp = await adapter.source_describe(SourceDescribeRequest())
    assert resp.source_type.value.lower() == "horreum"
    assert resp.contract_version.value == "1.0.0"


@pytest.mark.asyncio
async def test_horreum_runs_and_datasets_env_gated() -> None:
    """Exercise runs.list → datasets.search → datasets.get if env provides testId."""
    base_url = _get_env("HORREUM_BASE_URL")
    api_key = os.environ.get("HORREUM_API_KEY", "")
    test_id = _get_env("HORREUM_TEST_ID")
    schema_uri = _get_env("HORREUM_SCHEMA_URI")

    if not base_url or not test_id:
        pytest.skip(
            "HORREUM_BASE_URL or HORREUM_TEST_ID not set; skipping dataset flow"
        )

    adapter = HorreumAdapter(base_url, api_key, timeout=15)

    runs = await adapter.runs_list(
        RunsListRequest.model_validate({"test_id": test_id, "page_size": 1})
    )
    assert runs.pagination is not None

    ds_req = {"test_id": test_id, "page_size": 1}
    if schema_uri:
        ds_req["schema_uri"] = schema_uri
    datasets = await adapter.datasets_search(
        DatasetsSearchRequest.model_validate(ds_req)
    )
    assert datasets.pagination is not None

    if datasets.datasets:
        first = datasets.datasets[0]
        body = await adapter.datasets_get(
            DatasetsGetRequest.model_validate({"dataset_id": first.dataset_id})
        )
        # Content can be large; just assert we received a typed response
        assert body.content is not None
