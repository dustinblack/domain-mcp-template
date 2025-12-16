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


class _MockMCPClient:
    """Mock MCP client for testing Elasticsearch adapter."""

    def __init__(self, response_json: Dict[str, Any]) -> None:
        self._json = response_json

    async def call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Return mocked tool responses."""
        return self._json


@pytest.mark.asyncio
async def test_tests_list_parsing_with_mock() -> None:
    """Validate tests.list response parsing with a mocked client."""
    adapter = ElasticsearchAdapter("npx -y @modelcontextprotocol/server-elasticsearch")
    # Inject mock client via public testing hook
    adapter.inject_client_for_testing(
        _MockMCPClient(
            {
                "indices": ["logs-app-*", "logs-system-*"],
            }
        )
    )
    resp = await adapter.tests_list(TestsListRequest.model_validate({"page_size": 1}))
    assert len(resp.tests) == 1
    assert resp.tests[0].test_id == "logs-app-*"
    assert resp.pagination.has_more is True


@pytest.mark.asyncio
async def test_datasets_search_parsing_with_mock() -> None:
    """Validate datasets.search parsing with a mocked client."""
    adapter = ElasticsearchAdapter("npx -y @modelcontextprotocol/server-elasticsearch")
    adapter.inject_client_for_testing(
        _MockMCPClient(
            {
                "hits": {
                    "hits": [
                        {
                            "_id": "doc-123",
                            "_index": "logs-app-prod",
                            "_source": {
                                "@timestamp": "2024-12-15T10:30:00Z",
                                "level": "INFO",
                                "service": "payment-api",
                                "message": "Request processed",
                            },
                        }
                    ],
                    "total": {"value": 1},
                }
            }
        )
    )
    resp = await adapter.datasets_search(
        DatasetsSearchRequest.model_validate(
            {"test_id": "logs-app-prod", "page_size": 10}
        )
    )
    assert len(resp.datasets) == 1
    assert "logs-app-prod::doc-123" in resp.datasets[0].dataset_id
    assert resp.pagination.has_more is False
