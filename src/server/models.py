"""Tool request/response models for the Domain MCP server."""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator

from ..domain.models import MetricPoint
from ..schemas.source_mcp_contract import MergeStrategy


class GetKeyMetricsRequest(BaseModel):
    """Request model for get_key_metrics with dual input modes and plan option.

    Supported modes (mutually exclusive):
    - Raw mode: provide ``data`` (list of dataset JSON objects).
    - Source-driven mode: provide ``source_id`` and optional query fields.
    - Plan-only: set ``plan_only`` with ``source_id`` to receive a client
      execution plan (no data fetched by the server).

    Note: This model is only used by the /tools/get_key_metrics HTTP endpoint.
    The /api/query LLM endpoint bypasses Pydantic validation to ensure identical
    behavior with the MCP SSE path.
    """

    # Common fields
    dataset_types: List[str] = Field(
        default_factory=list,
        description="Plugin identifiers to apply.",
    )
    group_by: List[str] = Field(
        default_factory=list,
        description="Dimensions for grouping (not yet implemented).",
    )

    # Raw mode fields
    data: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of dataset JSON bodies (raw mode).",
    )

    # Source-driven fields
    source_id: str = Field(
        default="",
        description=(
            "Logical source identifier (adapter key). "
            "Optional - will auto-select first configured source if not provided."
        ),
    )
    test_id: str = Field(
        default="",
        description=(
            "Optional test filter for dataset search. "
            "If not provided, will auto-discover boot-time tests."
        ),
    )
    run_id: str = Field(
        default="",
        description=(
            "Optional run ID to fetch metrics for a specific test run. "
            "When provided, fetches label values for that run only. "
            "Takes precedence over test_id and time filters."
        ),
    )
    os_id: str = Field(
        default="",
        description=(
            "Optional OS identifier for filtering boot time results. "
            "Examples: 'rhel', 'autosd', 'rhivos' (alias for rhel). "
            "When provided, server applies server-side filtering by RHIVOS OS ID label."
        ),
    )
    schema_uri: str = Field(
        default="",
        description="Optional dataset schema filter.",
    )
    from_timestamp: str = Field(
        default="",
        description=(
            "Optional start time filter. Passed through to Horreum MCP "
            "for interpretation (supports ISO timestamps, epoch millis, or "
            "natural language like 'last week'). Defaults to last 30 days."
        ),
    )
    to_timestamp: str = Field(
        default="",
        description=(
            "Optional end time filter. Passed through to Horreum MCP "
            "for interpretation (supports ISO timestamps, epoch millis, or "
            "natural language like 'now'). Defaults to current time."
        ),
    )
    limit: int = Field(
        default=100,
        description=(
            "Page size for dataset fetching (source mode). "
            "The server automatically paginates to fetch ALL matching results. "
            "This parameter controls the page size, not the total number of results. "
            "Default 100 provides good performance for most queries."
        ),
    )
    merge_strategy: MergeStrategy = Field(
        default=MergeStrategy.PREFER_FAST,
        description=(
            "Data source merging strategy. Controls how the server retrieves and "
            "combines data from multiple sources (label values, datasets). "
            "'prefer_fast' (default): Try label values, fallback to datasets if empty. "
            "'comprehensive': Fetch from both sources and merge results. "
            "'labels_only': Only use label values, fail if unavailable. "
            "'datasets_only': Skip labels, go straight to datasets."
        ),
    )
    plan_only: bool = Field(
        default=False,
        description=(
            "If true, return a client execution plan (no fetching); requires source_id"
        ),
    )

    @model_validator(mode="after")
    def _validate_dual_input(self) -> "GetKeyMetricsRequest":
        has_data = len(self.data) > 0
        is_source_mode = bool(self.source_id)

        if has_data and is_source_mode:
            raise ValueError(
                "Provide either 'data' (raw) or 'source_id' (source), not both"
            )
        # Allow empty source_id and dataset_types - will be auto-configured
        if self.plan_only and not is_source_mode:
            raise ValueError("'plan_only' requires 'source_id'")
        if is_source_mode and self.limit <= 0:
            raise ValueError("'limit' must be a positive integer")
        return self


class GetKeyMetricsResponse(BaseModel):
    """Response model for get_key_metrics (raw points for now)."""

    metric_points: List[MetricPoint] = Field(default_factory=list)
    domain_model_version: str = Field("1.0.0")


class FetchPlanStep(BaseModel):
    """Single client-executed step for fetching datasets from a Source MCP."""

    tool: str
    args: Dict[str, Any]


class GetKeyMetricsPlanResponse(BaseModel):
    """Plan-only response for get_key_metrics."""

    fetch_plan: List[FetchPlanStep] = Field(default_factory=list)
    domain_model_version: str = Field("1.0.0")


class ComputeStatisticsRequest(BaseModel):
    """Stub request for compute_statistics (Phase 2)."""

    metric_ids: List[str]
    method: List[str] | None = None


class ComputeStatisticsResponse(BaseModel):
    """Stub response for compute_statistics (Phase 2)."""

    results: List[dict] = Field(default_factory=list)


class GenerateReportRequest(BaseModel):
    """Stub request for generate_report (Phase 2)."""

    template_id: str
    format: str = Field("markdown")


class GenerateReportResponse(BaseModel):
    """Stub response for generate_report (Phase 2)."""

    content: str
