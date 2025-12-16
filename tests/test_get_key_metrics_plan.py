"""Tests for get_key_metrics plan-only mode."""

from __future__ import annotations

import importlib

import pytest

from src.server.app import DomainMCPServer
from src.server.models import GetKeyMetricsRequest

# Ensure plugin registry is populated
importlib.import_module("src.domain.plugins.boot_time")


@pytest.mark.asyncio
async def test_get_key_metrics_plan_only() -> None:
    """Plan-only request should return a fetch plan with search and get steps."""
    server = DomainMCPServer()
    await server.start()

    req = GetKeyMetricsRequest.model_validate(
        {
            "dataset_types": ["boot-time-verbose"],
            "source_id": "horreum-stdio",
            "test_id": "t1",
            "schema_uri": "urn:boot-time-verbose:04",
            "limit": 3,
            "plan_only": True,
        }
    )

    plan = server.build_horreum_fetch_plan(
        test_id=req.test_id, schema_uri=req.schema_uri, limit=req.limit
    )

    assert len(plan) == 2
    assert plan[0]["tool"] == "datasets.search"
    assert plan[1]["tool"] == "datasets.get"

    await server.stop()
