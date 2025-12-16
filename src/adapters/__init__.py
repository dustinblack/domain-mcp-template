"""Source adapter interfaces and registry."""

from __future__ import annotations

import logging
from typing import Dict, Protocol

from ..schemas.source_mcp_contract import (  # Label values (Phase 2.5)
    ArtifactsGetRequest,
    ArtifactsGetResponse,
    DatasetLabelValuesRequest,
    DatasetLabelValuesResponse,
    DatasetsGetRequest,
    DatasetsGetResponse,
    DatasetsSearchRequest,
    DatasetsSearchResponse,
    RunLabelValuesRequest,
    RunLabelValuesResponse,
    RunsListRequest,
    RunsListResponse,
    SourceDescribeRequest,
    SourceDescribeResponse,
    TestLabelValuesRequest,
    TestLabelValuesResponse,
    TestsListRequest,
    TestsListResponse,
)


class SourceAdapter(Protocol):
    """Protocol for Source MCP adapters.

    Implementations translate Source MCP Contract tool calls to the underlying
    backend (e.g., Horreum MCP) and return validated responses.
    """

    async def source_describe(
        self, req: SourceDescribeRequest
    ) -> SourceDescribeResponse:
        """Return source metadata and contract support details."""
        raise NotImplementedError

    async def tests_list(self, req: TestsListRequest) -> TestsListResponse:
        """List tests with optional filtering and pagination."""
        raise NotImplementedError

    async def runs_list(self, req: RunsListRequest) -> RunsListResponse:
        """List runs for a test with optional time range and pagination."""
        raise NotImplementedError

    async def datasets_search(
        self, req: DatasetsSearchRequest
    ) -> DatasetsSearchResponse:
        """Search datasets across tests/runs with filters and pagination."""
        raise NotImplementedError

    async def datasets_get(self, req: DatasetsGetRequest) -> DatasetsGetResponse:
        """Fetch dataset content by identifier."""
        raise NotImplementedError

    async def artifacts_get(self, req: ArtifactsGetRequest) -> ArtifactsGetResponse:
        """Fetch a binary artifact linked to a run by name/path."""
        raise NotImplementedError

    # ---------------- Label values (Phase 2.5) ----------------
    async def get_run_label_values(
        self, req: RunLabelValuesRequest
    ) -> RunLabelValuesResponse:
        """Get label values for a specific run with optional filtering."""
        raise NotImplementedError

    async def get_test_label_values(
        self, req: TestLabelValuesRequest
    ) -> TestLabelValuesResponse:
        """Get aggregated label values across runs for a test (time-bounded)."""
        raise NotImplementedError

    async def get_dataset_label_values(
        self, req: DatasetLabelValuesRequest
    ) -> DatasetLabelValuesResponse:
        """Get label values for a specific dataset identifier."""
        raise NotImplementedError


_adapters: Dict[str, SourceAdapter] = {}


def register_adapter(source_id: str, adapter: SourceAdapter) -> None:
    """Register an adapter instance under a logical `source_id`."""
    _adapters[source_id] = adapter


def get_adapter(source_id: str) -> SourceAdapter:
    """Retrieve a registered adapter by `source_id`."""
    return _adapters[source_id]


def get_available_source_ids() -> list[str]:
    """Get list of registered adapter source_ids."""
    return list(_adapters.keys())


def log_adapter_status() -> None:
    """Log information about registered adapters and available functionality."""
    logger = logging.getLogger(__name__)

    if not _adapters:
        logger.warning(
            "No external MCP servers configured. Only raw mode functionality "
            "available.\n"
            "  - ✅ Raw mode: Analyze data you provide directly\n"
            "  - ❌ Source-driven mode: Requires external Horreum MCP server "
            "configuration\n"
            "  - 💡 To enable source-driven mode, set DOMAIN_MCP_CONFIG "
            "environment variable\n"
            "  - 📖 See documentation: https://github.com/dustinblack/horreum-mcp"
        )
    else:
        adapter_info = []
        for source_id, adapter in _adapters.items():
            adapter_type = type(adapter).__name__
            if "Bridge" in adapter_type:
                adapter_info.append(f"'{source_id}' (stdio bridge)")
            else:
                adapter_info.append(f"'{source_id}' (HTTP)")

        logger.info(
            "External MCP server connections configured: %s\n"
            "  - ✅ Raw mode: Available\n"
            "  - ✅ Source-driven mode: Available",
            ", ".join(adapter_info),
        )


def reset_adapters() -> None:
    """Test-only helper to clear registered adapters.

    This is used by functional tests to ensure a clean environment when
    asserting behaviors that depend on adapter presence/absence.
    """
    _adapters.clear()
