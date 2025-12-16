"""Minimal Elasticsearch adapter smoke tests with mocked HTTP.

These tests validate that the ElasticsearchAdapter serializes requests and parses
responses per the Source MCP Contract without requiring a live Elasticsearch MCP.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from src.adapters.elasticsearch import ElasticsearchAdapter
from src.schemas.source_mcp_contract import (
    DatasetsSearchRequest,
    SourceDescribeRequest,
    TestsListRequest,
)


@pytest.mark.asyncio
async def test_source_describe_static_fields() -> None:
    """Ensure describe returns expected capabilities and contract version."""
    adapter = ElasticsearchAdapter("npx -y @modelcontextprotocol/server-elasticsearch")
    resp = await adapter.source_describe(SourceDescribeRequest())
    assert resp.capabilities.pagination is True
    assert resp.contract_version.value == "1.0.0"
    assert resp.source_type.value == "elasticsearch"


class _MockClient:
    """Tiny mock of httpx.AsyncClient returning a fixed JSON payload."""

    def __init__(self, response_json: Dict[str, Any]) -> None:
        self._json = response_json

    async def post(self, _path: str, json: Dict[str, Any]) -> "_MockResponse":
        """Return a mocked response regardless of path/body."""
        return _MockResponse(self._json)

    async def aclose(self) -> None:
        """No-op async close for API parity with httpx.AsyncClient."""
        return None


class _MockResponse:
    """Minimal response object exposing raise_for_status/json methods."""

    def __init__(self, payload: Dict[str, Any]) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:  # no-op
        """Simulate successful HTTP status."""
        return None

    def json(self) -> Dict[str, Any]:
        """Return the preconfigured JSON payload."""
        return self._payload


@pytest.mark.asyncio
async def test_tests_list_parsing_with_mock() -> None:
    """Validate tests.list response parsing with a mocked client."""
    adapter = ElasticsearchAdapter("npx -y @modelcontextprotocol/server-elasticsearch")
    # Inject mock client via public testing hook
    adapter.inject_http_client_for_testing(
        _MockClient(
            {
                "tests": [
                    {"test_id": "logs-app-*", "name": "Application Logs", "description": "App log indices", "tags": []}
                ],
                "pagination": {"has_more": False},
            }
        )
    )
    resp = await adapter.tests_list(TestsListRequest.model_validate({"page_size": 1}))
    assert len(resp.tests) == 1
    assert resp.tests[0].test_id == "logs-app-*"
    assert resp.pagination.has_more is False


@pytest.mark.asyncio
async def test_datasets_search_parsing_with_mock() -> None:
    """Validate datasets.search parsing with a mocked client."""
    adapter = ElasticsearchAdapter("npx -y @modelcontextprotocol/server-elasticsearch")
    adapter.inject_http_client_for_testing(
        _MockClient(
            {
                "datasets": [
                    {
                        "dataset_id": "doc-123",
                        "test_id": "logs-app-*",
                        "content_type": "application/json",
                        "data": {
                            "@timestamp": "2024-12-15T10:30:00Z",
                            "level": "INFO",
                            "service": "payment-api",
                            "message": "Request processed"
                        }
                    }
                ],
                "pagination": {"has_more": False},
            }
        )
    )
    resp = await adapter.datasets_search(
        DatasetsSearchRequest.model_validate({"page_size": 1})
    )
    assert len(resp.datasets) == 1
    assert resp.datasets[0].dataset_id == "doc-123"
    assert resp.pagination.has_more is False

