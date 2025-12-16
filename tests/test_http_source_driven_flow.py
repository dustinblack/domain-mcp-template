"""Functional test for full source-driven flow (config → fetch → process)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.adapters import register_adapter
from src.schemas.source_mcp_contract import (
    DatasetLabelValuesRequest,
    DatasetLabelValuesResponse,
    DatasetsGetRequest,
    DatasetsGetResponse,
    DatasetsSearchRequest,
    DatasetsSearchResponse,
    RunLabelValuesRequest,
    RunLabelValuesResponse,
    TestLabelValuesRequest,
    TestLabelValuesResponse,
)
from src.server.http import create_app


class _FakeAdapter:
    """Stub SourceAdapter that returns a single boot-time dataset."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def datasets_search(
        self, req: DatasetsSearchRequest
    ) -> DatasetsSearchResponse:
        """Return a single dataset reference with no pagination."""
        _ = req
        return DatasetsSearchResponse.model_validate(
            {
                "datasets": [
                    {
                        "dataset_id": "d1",
                        "run_id": "r1",
                        "test_id": "t1",
                        "content_type": "application/json",
                    }
                ],
                "pagination": {"has_more": False},
            }
        )

    async def get_run_label_values(
        self, req: RunLabelValuesRequest
    ) -> RunLabelValuesResponse:
        """Stub: return empty label values (force fallback to datasets)."""
        _ = req
        return RunLabelValuesResponse.model_validate({"items": []})

    async def get_test_label_values(
        self, req: TestLabelValuesRequest
    ) -> TestLabelValuesResponse:
        """Stub: return empty label values (force fallback to datasets)."""
        _ = req
        return TestLabelValuesResponse.model_validate({"items": []})

    async def get_dataset_label_values(
        self, req: DatasetLabelValuesRequest
    ) -> DatasetLabelValuesResponse:
        """Stub: return empty label values (force fallback to datasets)."""
        _ = req
        return DatasetLabelValuesResponse.model_validate({"items": []})

    async def datasets_get(self, req: DatasetsGetRequest) -> DatasetsGetResponse:
        """Return the stored JSON payload for a given dataset id."""
        _ = req
        return DatasetsGetResponse.model_validate(
            {
                "dataset_id": "d1",
                "content": self._payload,
                "etag": None,
                "last_modified": None,
                "content_type": "application/json",
            }
        )


def test_source_driven_get_key_metrics_end_to_end():
    """End-to-end: register adapter, call source-driven endpoint, get metrics."""
    # Load a local boot-time fixture usable by the plugin
    fixture = Path(__file__).parent / "fixtures" / "boot-time" / "successful-boot.json"
    data = json.loads(fixture.read_text())

    # Register a fake adapter under source_id "s1"
    register_adapter("s1", _FakeAdapter(data))

    with patch.dict("os.environ", {"DOMAIN_MCP_HTTP_TOKEN": "t"}):
        app = create_app()
        c = TestClient(app)
        r = c.post(
            "/tools/get_key_metrics",
            headers={"Authorization": "Bearer t"},
            json={
                "dataset_types": ["boot-time-verbose"],
                "source_id": "s1",
                "test_id": "t1",
                "limit": 1,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("metric_points"), list)
        assert len(body["metric_points"]) >= 1
