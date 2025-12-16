"""Tests for MCP stdio bridge adapter using a mock client."""

from __future__ import annotations

import pytest

from src.adapters.mcp_bridge import MCPBridgeAdapter
from src.schemas.source_mcp_contract import (
    DatasetsGetRequest,
    DatasetsSearchRequest,
    RunsListRequest,
    SourceDescribeRequest,
    TestsListRequest,
)


class _MockMCPClient:
    async def call_tool(self, name: str, args: dict):  # pragma: no cover - trivial
        """Return canned responses for tool invocations (test helper)."""
        if name == "tests.list":
            return {"tests": [], "pagination": {"has_more": False}}
        if name == "runs.list":
            return {"runs": [], "pagination": {"has_more": False}}
        if name == "datasets.search":
            return {"datasets": [], "pagination": {"has_more": False}}
        if name == "datasets.get":
            return {
                "dataset_id": args.get("dataset_id", "d1"),
                "content": {},
                "content_type": "application/json",
            }
        if name == "artifacts.get":
            return {
                "run_id": args.get("run_id", "r1"),
                "name": args.get("name", "a"),
                "content": "",
                "content_type": "application/octet-stream",
                "size_bytes": 0,
            }
        raise AssertionError(f"Unexpected tool: {name}")


@pytest.mark.asyncio
async def test_bridge_describe_static() -> None:
    """Ensure bridge describe returns a valid contract version."""
    adapter = MCPBridgeAdapter()
    resp = await adapter.source_describe(SourceDescribeRequest())
    assert resp.contract_version.value == "1.0.0"


@pytest.mark.asyncio
async def test_bridge_list_calls_mock() -> None:
    """Exercise list/search/get calls via the stdio bridge mock client."""
    adapter = MCPBridgeAdapter()
    adapter.inject_client_for_testing(_MockMCPClient())

    tl = await adapter.tests_list(TestsListRequest.model_validate({}))
    assert tl.pagination.has_more is False

    rl = await adapter.runs_list(RunsListRequest.model_validate({"test_id": "t"}))
    assert rl.pagination.has_more is False

    ds = await adapter.datasets_search(DatasetsSearchRequest.model_validate({}))
    assert ds.pagination.has_more is False

    dg = await adapter.datasets_get(
        DatasetsGetRequest.model_validate({"dataset_id": "d"})
    )
    assert dg.dataset_id == "d"
