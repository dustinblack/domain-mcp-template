"""HTTP server exposing Domain MCP tools via FastAPI.

Endpoints implement a thin HTTP transport that maps requests to the same
tool handlers used by the stdio MCP server. Authentication and CORS are
configurable via environment variables.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, cast

import httpx
import psutil
from pydantic import BaseModel, Field, ValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

try:
    from fastapi_mcp import FastApiMCP  # type: ignore[import-untyped]
except ImportError:
    FastApiMCP = None  # type: ignore[assignment,misc]

from .. import __domain_model_version__, __version__
from ..adapters import (
    get_adapter,
    get_available_source_ids,
    log_adapter_status,
    register_adapter,
)
from ..adapters.horreum import HorreumAdapter
from ..adapters.mcp_bridge import MCPBridgeAdapter
from ..config.models import AppConfig, EnvSettings
from ..domain.models import MetricPoint
from ..domain.plugins import (
    all_plugins,
    apply_enabled_plugins,
)
from ..domain.plugins import get as get_plugin
from ..domain.plugins import (
    log_plugin_discovery_debug,
    log_plugin_status,
    reset_plugins,
)
from ..observability import setup_logging
from ..schemas.source_mcp_contract import (
    DatasetsGetRequest,
    DatasetsSearchRequest,
    MergeStrategy,
    TestsListRequest,
)
from ..utils.correlation import get_request_id, set_request_id
from ..utils.partial_results import fetch_datasets_with_fallback, format_failure_summary
from .app import DomainMCPServer
from .models import (
    FetchPlanStep,
    GetKeyMetricsPlanResponse,
    GetKeyMetricsRequest,
    GetKeyMetricsResponse,
)
from .normalize import normalize_get_key_metrics_params
from .resources import list_resources, read_resource

logger = logging.getLogger(__name__)


class MCPRequestLoggingMiddleware(
    BaseHTTPMiddleware
):  # pylint: disable=too-few-public-methods
    """Middleware to log all MCP-related HTTP requests for debugging.

    Logs:
    - All requests to /mcp endpoints (SSE and HTTP)
    - Request method, path, headers, and body (for POST)
    - Response status and timing
    - Special handling for MCP messages endpoint
    """

    async def dispatch(self, request: Request, call_next):
        """Log request details before and after processing."""
        start_time = time.time()
        path = request.url.path

        # Generate a per-request correlation id and store it
        req_id = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        set_request_id(req_id)

        # Log all MCP-related requests
        if path.startswith("/mcp"):
            # For POST requests to /mcp/messages, try to read body
            # But skip for SSE endpoint itself to avoid breaking streaming
            body_preview = ""
            if request.method == "POST" and "/mcp/messages/" in path:
                try:
                    # Read body for logging (this caches it for the handler)
                    body = await request.body()
                    # Limit body preview to 500 chars
                    body_str = body.decode("utf-8", errors="replace")
                    body_preview = (
                        body_str
                        if len(body_str) <= 500
                        else f"{body_str[:500]}... (truncated)"
                    )
                except Exception:
                    body_preview = "(unable to read body)"

            logger.info(
                "mcp.request.received",
                extra={
                    "req_id": req_id,
                    "method": request.method,
                    "path": path,
                    "query": str(request.url.query),
                    "client": request.client.host if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "content_type": request.headers.get("content-type", "none"),
                    "accept": request.headers.get("accept", "none"),
                    "body_preview": body_preview if body_preview else None,
                },
            )

        # Process request
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response for MCP requests
            if path.startswith("/mcp"):
                logger.info(
                    "mcp.request.completed",
                    extra={
                        "req_id": req_id,
                        "method": request.method,
                        "path": path,
                        "status": response.status_code,
                        "duration_ms": int(duration * 1000),
                    },
                )

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "mcp.request.failed",
                extra={
                    "req_id": req_id,
                    "method": request.method,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": int(duration * 1000),
                },
                exc_info=True,
            )
            raise


# Export helper functions so dead-code linters recognize runtime usage.
# FastAPI registers these via decorators; static analysis alone may not see
# direct references otherwise.
__all__ = [
    "create_app",
    "_load_fastapi",
    "_build_app",
    "_apply_cors_env",
    "_register_lifecycle",
    "_make_auth_dependency",
    "_register_health",
    "_register_resources",
    "_register_debug",
    "_register_tools",
]


class HealthResponse(BaseModel):
    """Simple health/readiness response model."""

    status: str


class ErrorResponse(BaseModel):
    """Structured JSON error response for HTTP endpoints.

    Fields
    ------
    detail: str
        Human-readable explanation of the error.
    error_type: str
        Machine-readable error classification.
    available_options: list[str] | None
        Optional list of valid options when the error is about an invalid
        input value (e.g., unknown `source_id` or dataset type).
    """

    detail: str = Field(..., description="Human-readable error detail")
    error_type: str = Field(..., description="Machine-readable error type")
    available_options: List[str] | None = Field(
        default=None, description="Optional list of valid alternative options"
    )


class CapabilitiesResponse(BaseModel):
    """Server capabilities summary for diagnostics and clients."""

    domain_version: str = Field("1.0.0")
    http_auth: str
    cors_origins: List[str]
    modes: Dict[str, bool]
    tools: List[str]
    plugins: List[str]
    sources: List[str]


class DebugExtractRequest(BaseModel):
    """Request for debug extraction endpoint."""

    dataset_json: Dict[str, Any] = Field(
        ...,
        description="Raw dataset JSON to test extraction with",
    )
    label_values: Optional[List[Any]] = Field(
        None,
        description="Optional label values to test label extraction path",
    )
    dataset_type: str = Field(
        "boot-time-verbose",
        description="Plugin ID to use for extraction",
    )
    run_type_filter: Optional[str] = Field(
        None,
        description="Optional run type filter to test filtering",
    )
    os_filter: Optional[str] = Field(
        None,
        description="Optional OS filter to test filtering",
    )


class DebugExtractResponse(BaseModel):
    """Response from debug extraction endpoint."""

    metrics_extracted: int
    metric_points: List[Dict[str, Any]]
    extraction_path: str
    filters_applied: Dict[str, Optional[str]]
    logs: List[str] = Field(
        default_factory=list,
        description="Extraction log messages captured during processing",
    )


class QueryRequest(BaseModel):
    """Natural language query request (Phase 6.1 - LLM integration)."""

    query: str = Field(
        ...,
        description="Natural language query about performance data",
        max_length=2000,
    )


class QueryResponse(BaseModel):
    """Natural language query response (Phase 6.1 - LLM integration)."""

    query: str = Field(description="The original query")
    answer: str = Field(description="The formatted answer from the LLM")
    metadata: Dict[str, Any] = Field(
        description="Execution metadata (tool_calls, llm_calls, duration_ms)"
    )
    tool_calls: List[Dict[str, Any]] = Field(description="Trace of tool executions")


# --------------------- MCP-over-HTTP shared helpers ---------------------


class MCPHTTPRequest(BaseModel):
    """JSON-RPC 2.0 request model for MCP-over-HTTP."""

    jsonrpc: str
    method: str
    id: str | int | None = None
    params: Dict[str, Any] | None = None


class MCPHTTPResponse(BaseModel):
    """JSON-RPC 2.0 response model for MCP-over-HTTP."""

    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: Dict[str, Any] | None = None


tools_available = ["get_key_metrics", "get_key_metrics_raw"]


def _ok(req_id: str | int | None, result: Any) -> Dict[str, Any]:
    """Build a JSON-RPC success envelope for the given result."""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _err(
    req_id: str | int | None, code: int, message: str, data: Any | None = None
) -> Dict[str, Any]:
    """Build a JSON-RPC error envelope with optional data payload."""
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


async def _auto_discover_test_id(
    adapter: Any, dataset_types: List[str], test_id: str
) -> str:
    """Auto-discover test ID for boot-time queries if not provided.

    This shared function ensures HTTP, LLM, and MCP SSE paths all use
    identical test discovery logic. It queries Horreum for tests matching
    the dataset type and falls back to known test IDs.

    Parameters
    ----------
    adapter : Any
        Horreum adapter for querying tests
    dataset_types : List[str]
        Dataset types being queried (e.g., ["boot-time-verbose"])
    test_id : str
        Current test_id value (empty string if not set)

    Returns
    -------
    str
        Discovered or fallback test_id, or original if already set
    """
    if test_id or not dataset_types:
        return test_id

    # Domain knowledge: map dataset types to known test patterns
    if "boot-time-verbose" in dataset_types:
        try:
            # Try exact match first with query filter
            tests_resp = await adapter.tests_list(
                TestsListRequest(
                    query="boot-time-verbose",
                    page_size=10,
                    tags=None,
                    page_token=None,
                )
            )
            exact_match = [
                t for t in tests_resp.tests if "boot-time-verbose" in t.name.lower()
            ]

            # If no exact match, try broader "boot" search
            if not exact_match:
                tests_resp = await adapter.tests_list(
                    TestsListRequest(
                        query="boot",
                        page_size=50,
                        tags=None,
                        page_token=None,
                    )
                )
                # Filter out framework boot tests
                exact_match = [
                    t
                    for t in tests_resp.tests
                    if "boot-time" in t.name.lower()
                    and "quarkus" not in t.name.lower()
                    and "spring" not in t.name.lower()
                ]

            if exact_match:
                test_id = exact_match[0].test_id
                logger.info(
                    "domain.boot_time.test_selected",
                    extra={
                        "name": exact_match[0].name,
                        "test_id": test_id,
                        "available": len(exact_match),
                    },
                )
            else:
                logger.warning("boot_time.no_tests_found", extra={"query": "boot"})
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.warning("boot_time.test_discovery_failed", extra={"error": str(e)})

        # Fall back to default boot-time test ID if still not found
        if not test_id and "boot-time-verbose" in dataset_types:
            test_id = "109"  # boot-time-verbose test in Horreum
            logger.info("boot_time.using_fallback_test_id", extra={"test_id": test_id})

    return test_id


async def _fetch_source_datasets(
    adapter: Any, req_model: Any  # GetKeyMetricsRequest or SimpleNamespace
) -> List[Dict[str, Any]]:
    """Fetch datasets via Source MCP adapter for source-driven mode.

    Automatically paginates through all results to ensure complete data coverage.
    The limit parameter controls the page size, not the total number of results.

    Uses partial results handling to continue fetching even if some datasets fail.
    Requires at least 50% success rate to return results.
    """
    search_payload: Dict[str, Any] = {
        "test_id": getattr(req_model, "test_id", ""),
        "schema_uri": getattr(req_model, "schema_uri", ""),
        "page_size": getattr(
            req_model, "limit", 100
        ),  # Used as page size, not total limit
    }

    # Add run_id filter if provided (takes precedence over time filters)
    run_id = getattr(req_model, "run_id", "")
    if run_id:
        # Convert single run_id to list format for DatasetsSearchRequest
        search_payload["run_ids"] = [run_id]
        logger.info(
            "fetch.datasets.run_id_filter",
            extra={"run_id": run_id, "note": "Fetching specific run only"},
        )

    from_ts = getattr(req_model, "from_timestamp", "")
    to_ts = getattr(req_model, "to_timestamp", "")
    if from_ts:
        search_payload["from"] = from_ts
    if to_ts:
        search_payload["to"] = to_ts

    dataset_ids: List[str] = []
    page_count = 0

    # First, collect all dataset IDs via pagination
    while True:
        page_count += 1
        logger.debug(
            "fetch.datasets.page",
            extra={"page": page_count, "page_size": req_model.limit},
        )

        search_resp = await adapter.datasets_search(
            DatasetsSearchRequest.model_validate(search_payload)
        )

        # Collect dataset IDs from this page
        dataset_ids.extend([ds.dataset_id for ds in search_resp.datasets])

        # Check if there are more pages
        if not search_resp.pagination.has_more:
            break

        # Get next page using pagination token
        if search_resp.pagination.next_page_token:
            search_payload["page_token"] = search_resp.pagination.next_page_token
        else:
            # No token provided but has_more=True, break to avoid infinite loop
            logger.warning(
                "Pagination indicated has_more=True but no next_page_token provided"
            )
            break

    # Handle empty result set
    if not dataset_ids:
        logger.info(
            "fetch.datasets.done",
            extra={"total": 0, "pages": page_count},
        )
        return []

    # Fetch all datasets with partial results handling (50% success rate required)
    result = await fetch_datasets_with_fallback(
        adapter, dataset_ids, min_success_rate=0.5
    )

    # Log if there were any failures
    if result.has_failures:
        summary = format_failure_summary(result, "dataset fetch")
        logger.warning("fetch.datasets.partial_failure", extra={"summary": summary})

    logger.info(
        "fetch.datasets.done",
        extra={
            "total": len(result.successes),
            "pages": page_count,
            "failures": len(result.failures),
            "success_rate": result.success_rate,
        },
    )

    return result.successes


async def _call_get_key_metrics_raw(
    app_server: DomainMCPServer, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Call raw-mode metrics extraction via Domain MCP server.

    This function bypasses Pydantic validation and works directly with
    normalized parameters, making it behave identically to the MCP SSE path.
    """

    # Normalize parameters
    normalized = normalize_get_key_metrics_params(params)

    # Extract filter hints (internal metadata)
    os_filter_hint = normalized.pop("_detected_os_filter", None)
    run_type_hint = normalized.pop("_detected_run_type", None)

    # Extract parameters with defaults (no Pydantic validation!)
    dataset_types = normalized.get("dataset_types", [])
    data = normalized.get("data", [])

    # Call the raw extraction method
    points = await app_server.get_key_metrics_raw(
        dataset_types,
        cast(List[object], data),
        os_filter=os_filter_hint,
        run_type_filter=run_type_hint,
    )
    return {
        "metric_points": [
            (p.model_dump() if hasattr(p, "model_dump") else p) for p in points
        ],
        "domain_model_version": "1.0.0",
    }


def _merge_metric_points(
    label_points: List[MetricPoint],
    dataset_points: List[MetricPoint],
    strategy: MergeStrategy,
) -> List[MetricPoint]:
    """Merge and de-duplicate metric points from multiple sources.

    De-duplication strategy:
    - For COMPREHENSIVE mode: Label values take precedence (they're pre-aggregated)
    - De-duplicate based on (metric_id, timestamp) tuple
    - Preserve source annotation to show data provenance

    Args:
        label_points: Metrics extracted from label values
        dataset_points: Metrics extracted from raw datasets
        strategy: Merge strategy being used

    Returns:
        Merged list of metric points
    """

    # For non-comprehensive strategies, return appropriate list
    if strategy != MergeStrategy.COMPREHENSIVE:
        if strategy == MergeStrategy.DATASETS_ONLY:
            return dataset_points
        if strategy == MergeStrategy.LABELS_ONLY:
            return label_points
        # PREFER_FAST
        return label_points if label_points else dataset_points

    # COMPREHENSIVE mode: merge both sources with de-duplication
    # Use dict with (metric_id, timestamp) as key to deduplicate
    merged: Dict[tuple[str, str], MetricPoint] = {}

    # Add dataset points first (lower priority)
    for point in dataset_points:
        key = (point.metric_id, point.timestamp.isoformat())
        merged[key] = point

    # Add label points second (higher priority, overwrites duplicates)
    for point in label_points:
        key = (point.metric_id, point.timestamp.isoformat())
        merged[key] = point

    # Convert back to list, sorted by timestamp then metric_id for consistency
    result = sorted(merged.values(), key=lambda p: (p.timestamp, p.metric_id))

    if label_points and dataset_points:
        logger.info(
            "merge.deduplication",
            extra={
                "label_points": len(label_points),
                "dataset_points": len(dataset_points),
                "merged_points": len(result),
                "duplicates_removed": len(label_points)
                + len(dataset_points)
                - len(result),
            },
        )

    return result


async def _fetch_from_sources(
    app_server: DomainMCPServer,
    req_model: Any,  # GetKeyMetricsRequest or SimpleNamespace with same attributes
    os_filter_hint: str | None,
    run_type_hint: str | None,
) -> tuple[List[MetricPoint], List[MetricPoint]]:
    """Fetch metrics from label values and/or datasets based on merge strategy.

    Returns:
        Tuple of (label_points, dataset_points) - either may be empty based on strategy
    """
    label_points: List[MetricPoint] = []
    dataset_points: List[MetricPoint] = []

    # Determine what to fetch based on merge strategy
    fetch_labels = req_model.merge_strategy in (
        MergeStrategy.PREFER_FAST,
        MergeStrategy.COMPREHENSIVE,
        MergeStrategy.LABELS_ONLY,
    )
    fetch_datasets = req_model.merge_strategy in (
        MergeStrategy.DATASETS_ONLY,
        MergeStrategy.COMPREHENSIVE,
    )

    # Fetch from label values if needed
    if fetch_labels:
        lv_items = await app_server.prefer_label_values_when_available(
            req_model.dataset_types,
            test_id=(req_model.test_id or None),
            run_id=(req_model.run_id or None),
            source_id=req_model.source_id,
            before=(req_model.to_timestamp or None),
            after=(req_model.from_timestamp or None),
            page_size=req_model.limit,
            os_filter=os_filter_hint,
            run_type_filter=run_type_hint,
        )
        if lv_items:
            plugin = get_plugin(req_model.dataset_types[0])
            label_points = await plugin.extract(  # type: ignore[call-arg]
                json_body={},
                refs={},
                label_values=lv_items,  # type: ignore[arg-type]
                run_type_filter=run_type_hint,
                os_filter=os_filter_hint,
            )
            logger.info(
                "fetch.label_values.complete",
                extra={
                    "points": len(label_points),
                    "strategy": req_model.merge_strategy.value,
                },
            )

    # For PREFER_FAST, only fetch datasets if labels were empty
    if req_model.merge_strategy == MergeStrategy.PREFER_FAST:
        if label_points:
            return (label_points, [])
        # Labels empty, now try datasets
        fetch_datasets = True

    # Fetch from datasets if needed
    if fetch_datasets:
        try:
            adapter = get_adapter(req_model.source_id)
        except KeyError as exc:
            raise KeyError(f"unknown_source_id::{req_model.source_id}") from exc
        try:
            dataset_bodies = await _fetch_source_datasets(adapter, req_model)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"upstream_error::{str(exc)}") from exc

        # Extract metrics from datasets with streaming
        dataset_points = await app_server.get_key_metrics_raw(
            req_model.dataset_types,
            cast(List[object], dataset_bodies),
            os_filter=os_filter_hint,
            run_type_filter=run_type_hint,
        )
        logger.info(
            "fetch.datasets.complete",
            extra={
                "points": len(dataset_points),
                "strategy": req_model.merge_strategy.value,
            },
        )

    # Handle LABELS_ONLY failure case
    if req_model.merge_strategy == MergeStrategy.LABELS_ONLY and not label_points:
        raise ValueError(
            "merge_strategy=labels_only but no label values available. "
            "Label values may not be supported for this query or data source."
        )

    return (label_points, dataset_points)


async def _call_get_key_metrics(
    app_server: DomainMCPServer, params: Dict[str, Any]
) -> Dict[str, Any]:
    """Call source-driven or raw get_key_metrics via Domain MCP server.

    This function bypasses Pydantic validation and works directly with
    normalized parameters, making it behave identically to the MCP SSE path.
    All parameter validation happens naturally through Python function
    signatures and the underlying adapter implementations.
    """

    # Normalize parameters (handles aliases, type coercion, domain knowledge)
    normalized = normalize_get_key_metrics_params(params)

    # Extract filter hints (internal metadata, not part of the tool API)
    os_filter_hint = normalized.pop("_detected_os_filter", None)
    run_type_hint = normalized.pop("_detected_run_type", None)

    # Extract parameters with defaults (no Pydantic validation!)
    plan_only = normalized.get("plan_only", False)
    data = normalized.get("data", [])
    source_id = normalized.get("source_id", "")
    dataset_types = normalized.get("dataset_types", [])
    test_id = normalized.get("test_id", "")
    run_id = normalized.get("run_id", "")
    schema_uri = normalized.get("schema_uri", "")
    from_timestamp = normalized.get("from", "")  # Note: normalized to "from"
    to_timestamp = normalized.get("to", "")  # Note: normalized to "to"
    limit = normalized.get("limit", 100)
    merge_strategy_str = normalized.get("merge_strategy", "prefer_fast")

    # Convert merge_strategy string to enum
    merge_strategy = MergeStrategy(merge_strategy_str)

    # Handle plan_only mode
    if plan_only:
        plan = app_server.build_horreum_fetch_plan(
            test_id=test_id,
            schema_uri=schema_uri,
            limit=limit,
        )
        return {
            "fetch_plan": [FetchPlanStep.model_validate(s).model_dump() for s in plan],
            "domain_model_version": "1.0.0",
        }

    # Handle raw mode (data provided)
    if data and len(data) > 0:
        points = await app_server.get_key_metrics_raw(
            dataset_types,
            cast(List[object], data),
            os_filter=os_filter_hint,
            run_type_filter=run_type_hint,
        )
        return {
            "metric_points": [
                (p.model_dump() if hasattr(p, "model_dump") else p) for p in points
            ],
            "domain_model_version": "1.0.0",
        }

    # Source-driven mode
    # Auto-configure source_id if not provided
    if not source_id:
        available_sources = get_available_source_ids()
        if available_sources:
            source_id = available_sources[0]
            logger.info(
                "auto.source_id",
                extra={"source_id": source_id},
            )
        else:
            raise KeyError(
                "missing_source_id::No sources configured. "
                "Configure DOMAIN_MCP_CONFIG or provide 'data' for raw mode."
            )

    # Auto-configure dataset_types if not provided
    if not dataset_types:
        dataset_types = ["boot-time-verbose"]
        logger.info(
            "auto.dataset_types", extra={"dataset_types": ["boot-time-verbose"]}
        )

    # Auto-discover test_id if not provided (skip if run_id is provided)
    if not run_id:
        try:
            adapter = get_adapter(source_id)
            test_id = await _auto_discover_test_id(adapter, dataset_types, test_id)
        except KeyError:
            # No adapter configured, skip auto-discovery
            pass
    else:
        # When run_id is provided, log it and skip test discovery
        logger.info(
            "run_id.provided",
            extra={"run_id": run_id, "note": "Fetching specific run only"},
        )

    # Log OS filtering if detected
    if os_filter_hint:
        logger.info(
            "os_filter.detected",
            extra={"os_filter": os_filter_hint, "label": "RHIVOS OS ID"},
        )

    # Log query start for timeout troubleshooting
    query_start = time.time()
    logger.info(
        "query.start",
        extra={
            "dataset_types": dataset_types,
            "test_id": test_id,
            "run_id": run_id,
            "os_filter": os_filter_hint,
            "merge_strategy": merge_strategy.value,
            "from": from_timestamp,
            "to": to_timestamp,
        },
    )

    # Create a simple parameter object for _fetch_from_sources
    # (it needs an object with attributes, not a dict)
    req_params = SimpleNamespace(
        source_id=source_id,
        dataset_types=dataset_types,
        test_id=test_id,
        run_id=run_id,
        schema_uri=schema_uri,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        limit=limit,
        merge_strategy=merge_strategy,
        os_id=normalized.get("os_id", ""),
    )

    # Fetch from sources based on merge strategy
    label_points, dataset_points = await _fetch_from_sources(
        app_server, req_params, os_filter_hint, run_type_hint
    )

    # Merge and de-duplicate points
    points = _merge_metric_points(label_points, dataset_points, merge_strategy)

    query_duration = time.time() - query_start
    logger.info(
        "query.complete",
        extra={
            "duration_sec": round(query_duration, 2),
            "points": len(points),
            "label_points": len(label_points),
            "dataset_points": len(dataset_points),
            "strategy": merge_strategy.value,
        },
    )
    return {
        "metric_points": [p.model_dump() for p in points],
        "domain_model_version": "1.0.0",
    }


def _load_fastapi():
    """Dynamically import FastAPI pieces to keep deps optional."""
    fastapi_mod = importlib.import_module("fastapi")
    cors_mod = importlib.import_module("fastapi.middleware.cors")
    rq_mod = importlib.import_module("fastapi.requests")
    exc_mod = importlib.import_module("fastapi.exceptions")
    resp_mod = importlib.import_module("fastapi.responses")
    st_exc_mod = importlib.import_module("starlette.exceptions")
    return {
        "fastapi_cls": getattr(fastapi_mod, "FastAPI"),
        "depends": getattr(fastapi_mod, "Depends"),
        "header": getattr(fastapi_mod, "Header"),
        "body": getattr(fastapi_mod, "Body"),
        "http_exc": getattr(fastapi_mod, "HTTPException"),
        "status": getattr(fastapi_mod, "status"),
        "cors_mw": getattr(cors_mod, "CORSMiddleware"),
        "req": getattr(rq_mod, "Request"),
        "validation_exc": getattr(exc_mod, "RequestValidationError"),
        "json_response": getattr(resp_mod, "JSONResponse"),
        "starlette_http_exc": getattr(st_exc_mod, "HTTPException"),
    }


def _build_app(fastapi_cls: Any, lifespan: Any | None = None):
    """Create base FastAPI app (optionally with lifespan)."""
    if lifespan is not None:
        return fastapi_cls(
            title="Domain MCP Server", version=__version__, lifespan=lifespan
        )
    return fastapi_cls(title="Domain MCP Server", version=__version__)


def _apply_cors_env(app: Any, cors_middleware_cls: Any) -> None:
    """Enable CORS if DOMAIN_MCP_CORS_ORIGINS is set."""
    allow_origins: List[str] = []
    origins = os.environ.get("DOMAIN_MCP_CORS_ORIGINS", "")
    if origins:
        allow_origins = [o.strip() for o in origins.split(",") if o.strip()]
    if allow_origins:
        app.add_middleware(
            cors_middleware_cls,
            allow_origins=allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )


def _register_lifecycle(app: Any, server: DomainMCPServer) -> None:  # noqa: D401
    """Deprecated placeholder; lifecycle handled via lifespan in create_app."""
    _ = (app, server)


def _make_auth_dependency(header: Any, http_exc: Any, status_mod: Any):
    """Return a dependency function that enforces optional bearer token."""

    def _auth_dependency(authorization: str | None = header(default=None)) -> None:
        expected = _get_expected_token()
        if expected is None:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise http_exc(status_code=status_mod.HTTP_401_UNAUTHORIZED)
        token = authorization.split(" ", 1)[1]
        if token != expected:
            raise http_exc(status_code=status_mod.HTTP_403_FORBIDDEN)

    return _auth_dependency


def _register_health(app: Any) -> None:
    """Register health and readiness endpoints."""

    @app.get(
        "/health",
        response_model=HealthResponse,
        summary="Liveness probe",
    )
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/ready",
        response_model=HealthResponse,
        summary="Readiness probe",
    )
    async def ready() -> HealthResponse:
        return HealthResponse(status="ready")


def _register_capabilities(app: Any) -> None:
    """Register server capabilities endpoint."""

    @app.get(
        "/capabilities",
        response_model=CapabilitiesResponse,
        summary="Server capabilities summary",
    )
    async def capabilities() -> CapabilitiesResponse:  # noqa: D401
        token = _get_expected_token()
        cors = os.environ.get("DOMAIN_MCP_CORS_ORIGINS", "")
        cors_list = [o.strip() for o in cors.split(",") if o.strip()]
        source_ids = get_available_source_ids()
        # tools reflect HTTP endpoints currently exposed
        tools = [
            "get_key_metrics",
            "get_key_metrics_raw",
        ]
        plugins = [p.id for p in all_plugins()]
        return CapabilitiesResponse(
            domain_version=__domain_model_version__,
            http_auth=("enabled" if token else "disabled"),
            cors_origins=cors_list,
            modes={
                "raw": True,
                "source_driven": bool(source_ids),
            },
            tools=tools,
            plugins=plugins,
            sources=source_ids,
        )


def _register_resources(app: Any) -> None:
    """Register MCP resource endpoints for domain knowledge exposure."""

    class ResourceListResponse(BaseModel):
        """Response model for resource list."""

        resources: List[Dict[str, Any]] = Field(
            description="List of available MCP resources"
        )

    class ResourceReadResponse(BaseModel):
        """Response model for resource read."""

        contents: List[Dict[str, Any]] = Field(description="Resource contents")

    @app.get(
        "/resources",
        response_model=ResourceListResponse,
        summary="List MCP resources",
        description="List all available MCP resources (domain knowledge)",
    )
    async def list_mcp_resources() -> ResourceListResponse:
        """List all available MCP resources."""
        resources = list_resources()
        return ResourceListResponse(resources=resources)

    @app.get(
        "/resources/{resource_path:path}",
        response_model=ResourceReadResponse,
        summary="Read MCP resource",
        description="Read a specific MCP resource by path",
        responses={
            404: {
                "model": ErrorResponse,
                "description": "Resource not found",
            }
        },
    )
    async def read_mcp_resource(resource_path: str) -> ResourceReadResponse:
        """Read a specific MCP resource by path."""
        # Reconstruct URI from path
        uri = f"domain://{resource_path}"
        result = read_resource(uri)
        if result is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"Resource not found: {uri}")
        return ResourceReadResponse(**result)


def _register_debug(app: Any) -> None:
    """Register debug endpoints for extraction testing."""

    @app.post(
        "/debug/extract",
        response_model=DebugExtractResponse,
        summary="Debug extraction logic",
        description=(
            "Test extraction logic with provided dataset JSON and/or label "
            "values. Returns extracted metrics and detailed logging. "
            "Useful for debugging production data issues."
        ),
    )
    async def debug_extract(
        request: DebugExtractRequest,
    ) -> DebugExtractResponse:
        """Test extraction logic with provided data."""
        # Get the plugin
        plugin = get_plugin(request.dataset_type)
        if not plugin:
            return DebugExtractResponse(
                metrics_extracted=0,
                metric_points=[],
                extraction_path="error",
                filters_applied={
                    "run_type": request.run_type_filter,
                    "os": request.os_filter,
                },
                logs=[f"Plugin {request.dataset_type} not found"],
            )

        # Capture logs during extraction
        extraction_logs: List[str] = []
        original_handlers = logger.handlers[:]

        class LogCapture(logging.Handler):
            """Capture log messages during extraction."""

            def emit(self, record: logging.LogRecord) -> None:
                if record.name.startswith("domain.plugins.boot_time"):
                    extraction_logs.append(f"{record.levelname}: {record.getMessage()}")

        log_capture = LogCapture()
        log_capture.setLevel(logging.DEBUG)
        logger.addHandler(log_capture)

        try:
            # Call extract method
            points = await plugin.extract(  # type: ignore[call-arg]
                json_body=request.dataset_json,
                refs={},
                label_values=request.label_values,
                run_type_filter=request.run_type_filter,
                os_filter=request.os_filter,
            )

            extraction_path = "label_values" if request.label_values else "dataset"

            return DebugExtractResponse(
                metrics_extracted=len(points),
                metric_points=[
                    {
                        "metric_id": p.metric_id,
                        "timestamp": p.timestamp.isoformat(),
                        "value": p.value,
                        "unit": p.unit,
                        "dimensions": p.dimensions,
                        "source": p.source,
                    }
                    for p in points
                ],
                extraction_path=extraction_path,
                filters_applied={
                    "run_type": request.run_type_filter,
                    "os": request.os_filter,
                },
                logs=extraction_logs,
            )
        finally:
            logger.removeHandler(log_capture)
            # Restore original handlers
            logger.handlers = original_handlers


def _register_tools(  # noqa: ARG001
    app: Any,
    server: DomainMCPServer,
    depends: Any,
    http_exc: Any,
    auth_dep: Any,
    body: Any = None,
) -> None:
    """Register tool endpoints (get_key_metrics, get_key_metrics_raw)."""

    @app.post(
        "/tools/get_key_metrics",
        operation_id="get_key_metrics",
        response_model=GetKeyMetricsResponse,
        dependencies=[depends(auth_dep)],
        tags=["mcp-tools"],
        summary="Get boot time and performance metrics",
        description=(
            "PRIMARY TOOL for boot time and performance analysis queries. "
            "AUTO-CONFIGURATION (all parameters optional): "
            "source_id → first available, "
            "dataset_types → ['boot-time-verbose'], "
            "test_id → auto-discovers tests, "
            "limit → page size (100), server paginates ALL results. "
            "RUN ID QUERIES: "
            "Use run_id parameter to fetch specific Horreum run (e.g., '123456'). "
            "When run_id provided, fetches only that run (ignores time filters). "
            "CRITICAL CONSTRAINTS: "
            "NEVER use test_id for boot time queries (auto-discovery works). "
            "OS identifiers (e.g. rhel, autosd) are LABELS not test IDs. "
            "Platform names (e.g. qemu, intel-nuc) are LABELS not test IDs. "
            "Statistical calculations: server-side ONLY (deterministic). "
            "Results organized by: target × mode × os_id (3D matrix). "
            "COMMON PATTERNS: "
            "'Boot times last 30 days' → {from_timestamp: 'last 30 days'}, "
            "'RHEL boot performance' → {os_id: 'rhel'}, "
            "'Nightly runs last week' → {from_timestamp: 'last week'}, "
            "'Show statistics' → Returns all 7 metrics. "
            "DEFAULT RETURNS: "
            "Boot Phases (kernel_pre_timer, kernel, initrd, switchroot, "
            "system_init), "
            "Total (sum of phases, missing=0, noted in missing_phases "
            "dimension), "
            "KPIs (early_service, start_kmod_load, first_service, "
            "network_online), "
            "Statistics when requested (min, mean, max, p95, p99, std_dev, "
            "CV). "
            "RESULT STRUCTURE: "
            "metric_id (phase/total/KPI identifier), "
            "timestamp (test execution time), "
            "value (milliseconds), "
            "dimensions ({os_id, mode, target} for 3D grouping), "
            "source (label_values or dataset). "
            "3D MATRIX ORGANIZATION (REQUIRED): "
            "Group by dimensions.target (platform), "
            "dimensions.mode (image type), dimensions.os_id (OS variant). "
            "Enables platform/mode/OS comparison. "
            "REPORT METADATA (for reports): "
            "All available in dimensions: os_id, mode, target, release, "
            "image_name, samples, user, build. "
            "From timestamp: start time. "
            "Note: All metadata now on fast path (no dataset query needed). "
            "FILTERING: OS via os_id parameter. "
            "Platform from dimensions.target after query, "
            "Run Type detected from context (nightly, ci, release, manual). "
            "See docs/domain-glossary.md § Boot Time Domain for complete "
            "reference."
        ),
        responses={
            400: {"model": ErrorResponse},
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            404: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    async def get_key_metrics_http(
        req: GetKeyMetricsRequest = (
            body(default_factory=GetKeyMetricsRequest)
            if body
            else GetKeyMetricsRequest()
        ),
    ) -> GetKeyMetricsResponse:
        logger.debug(
            "http.get_key_metrics",
            extra={
                "req_id": get_request_id(),
                "has_data": bool(req.data),
                "source_id": req.source_id,
            },
        )
        if req.plan_only:
            logger.info(
                "http.get_key_metrics.plan_only", extra={"req_id": get_request_id()}
            )
            plan = server.build_horreum_fetch_plan(
                test_id=req.test_id, schema_uri=req.schema_uri, limit=req.limit
            )
            return GetKeyMetricsPlanResponse(
                fetch_plan=[FetchPlanStep.model_validate(s) for s in plan],
                domain_model_version=__domain_model_version__,
            )  # type: ignore[return-value]

        dataset_bodies: List[Dict[str, Any]]
        if req.data and len(req.data) > 0:
            dataset_bodies = req.data
        else:
            # Auto-configure source_id if not provided
            if not req.source_id:
                available_sources = get_available_source_ids()
                if available_sources:
                    req.source_id = available_sources[0]
                    logger.info(
                        "auto.source_id",
                        extra={
                            "req_id": get_request_id(),
                            "source_id": req.source_id,
                            "available": available_sources,
                        },
                    )
                else:
                    raise http_exc(
                        status_code=400,
                        detail=ErrorResponse(
                            detail=(
                                "No external Horreum MCP server configured. "
                                "Configure DOMAIN_MCP_CONFIG or provide 'data' "
                                "for raw mode."
                            ),
                            error_type="missing_configuration",
                            available_options=None,
                        ).model_dump(),
                    )
            try:
                adapter = get_adapter(req.source_id)
            except KeyError as exc:
                available = get_available_source_ids()
                if not available:
                    detail = (
                        "No external Horreum MCP server connection configured. "
                        "Configure DOMAIN_MCP_CONFIG to enable source-driven mode, "
                        "or use raw mode by providing 'data'."
                    )
                else:
                    detail = (
                        f"Source ID '{req.source_id}' not found. Check your "
                        f"DOMAIN_MCP_CONFIG."
                    )
                err = ErrorResponse(
                    detail=detail,
                    error_type="unknown_source_id",
                    available_options=available or None,
                )
                raise http_exc(status_code=404, detail=err.model_dump()) from exc

            # Default dataset_types to boot-time-verbose if not provided
            if not req.dataset_types:
                req.dataset_types = ["boot-time-verbose"]
                logger.info(
                    "Auto-configured dataset_types: ['boot-time-verbose']",
                    extra={"req_id": get_request_id()},
                )

            # Handle OS filtering
            os_filter_hint = None
            if req.os_id:
                # Normalize OS aliases
                os_alias_map = {"example-os-alias": "example-os"}  # Example mapping
                os_filter_hint = os_alias_map.get(req.os_id.lower(), req.os_id.lower())
                logger.info(
                    "os_filter.detected",
                    extra={
                        "req_id": get_request_id(),
                        "os_filter": os_filter_hint,
                        "label": "OS ID",
                    },
                )

            # Handle run type filtering (nightly, CI, release, manual)
            # Detect if test_id contains a run type keyword
            # (common AI misinterpretation)
            run_type_hint: Optional[str] = None
            known_run_types = {"nightly", "ci", "release", "manual", "ad-hoc", "adhoc"}
            test_id_lower = req.test_id.lower() if req.test_id else ""
            if test_id_lower in known_run_types:
                run_type_hint = test_id_lower
                # Clear the incorrect test_id, let auto-discovery work
                req.test_id = ""
                logger.info(
                    "run_type.detected_in_test_id",
                    extra={
                        "req_id": get_request_id(),
                        "run_type": run_type_hint,
                        "corrected": "Cleared test_id, will use label filtering",
                    },
                )

            # Log query start for timeout troubleshooting
            import time

            query_start = time.time()
            logger.info(
                "query.start",
                extra={
                    "req_id": get_request_id(),
                    "dataset_types": req.dataset_types,
                    "test_id": req.test_id,
                    "os_filter": os_filter_hint,
                    "from": req.from_timestamp,
                    "to": req.to_timestamp,
                },
            )

            # Translate domain concepts to Horreum test identifiers
            # The Domain MCP understands "boot time" and knows which tests to query
            if not req.test_id and req.dataset_types:
                # Domain knowledge: map dataset types to known test patterns
                if "boot-time-verbose" in req.dataset_types:
                    # Try to discover boot-time-verbose tests from Horreum
                    # Look for exact match first, then broader patterns
                    # Use Horreum MCP's query filter for efficient search
                    try:
                        # Try exact match first with query filter
                        tests_resp = await adapter.tests_list(
                            TestsListRequest(
                                query="boot-time-verbose",
                                page_size=10,
                                tags=None,
                                page_token=None,
                            )
                        )
                        exact_match = [
                            t
                            for t in tests_resp.tests
                            if "boot-time-verbose" in t.name.lower()
                        ]

                        # If no exact match, try broader "boot" search
                        if not exact_match:
                            tests_resp = await adapter.tests_list(
                                TestsListRequest(
                                    query="boot",
                                    page_size=50,
                                    tags=None,
                                    page_token=None,
                                )
                            )
                            # Filter out framework boot tests
                            exact_match = [
                                t
                                for t in tests_resp.tests
                                if "boot-time" in t.name.lower()
                                and "quarkus" not in t.name.lower()
                                and "spring" not in t.name.lower()
                            ]

                        selected_tests = exact_match
                        if selected_tests:
                            req.test_id = selected_tests[0].test_id
                            logger.info(
                                "domain.boot_time.test_selected",
                                extra={
                                    "req_id": get_request_id(),
                                    "name": selected_tests[0].name,
                                    "test_id": req.test_id,
                                    "available": len(selected_tests),
                                },
                            )
                        else:
                            logger.warning(
                                "boot_time.no_tests_found",
                                extra={"req_id": get_request_id(), "query": "boot"},
                            )
                    except (httpx.HTTPError, KeyError, ValueError) as e:
                        logger.warning(
                            "boot_time.test_discovery_failed",
                            extra={"req_id": get_request_id(), "error": str(e)},
                        )
                        # Fall back to default boot-time test ID
                        # This is a known test ID in the production Horreum instance
                        if not req.test_id and "boot-time-verbose" in req.dataset_types:
                            req.test_id = "109"  # boot-time-verbose test in Horreum
                            logger.info(
                                "boot_time.using_fallback_test_id",
                                extra={
                                    "req_id": get_request_id(),
                                    "test_id": req.test_id,
                                },
                            )

            # Now try label values fast path if we have a test_id
            if req.test_id:
                lv_items = await server.prefer_label_values_when_available(
                    req.dataset_types,
                    test_id=req.test_id,
                    run_id=None,
                    source_id=req.source_id,
                    before=req.to_timestamp or None,
                    after=req.from_timestamp or None,
                    page_size=req.limit,
                    os_filter=os_filter_hint,
                    run_type_filter=run_type_hint,
                )
                if lv_items:
                    # Use plugin extraction from label values
                    from ..domain.plugins import get as get_plugin

                    plugin = get_plugin(req.dataset_types[0])
                    points = await plugin.extract(  # type: ignore[call-arg]
                        json_body={},
                        refs={},
                        label_values=lv_items,  # type: ignore[arg-type]
                        run_type_filter=run_type_hint,
                        os_filter=os_filter_hint,
                    )
                    query_duration = time.time() - query_start
                    logger.info(
                        "query.complete",
                        extra={
                            "req_id": get_request_id(),
                            "duration_sec": round(query_duration, 2),
                            "points": len(points),
                            "path": "label_values",
                        },
                    )
                    return GetKeyMetricsResponse(
                        metric_points=points,
                        domain_model_version=__domain_model_version__,
                    )

            # Note: Time-based query interpretation ("last week", etc.) should
            # be handled by Horreum MCP, not here. We just pass through the
            # time parameters. If no time range is provided, Horreum MCP will
            # apply its default behavior.

            # Delegate to Horreum MCP for dataset search and filtering
            # Domain MCP has translated the query; Horreum MCP does the heavy lifting
            search_payload: Dict[str, Any] = {
                "test_id": req.test_id,
                "schema_uri": req.schema_uri,
                "page_size": req.limit,
            }
            if req.from_timestamp:
                search_payload["from"] = req.from_timestamp
            if req.to_timestamp:
                search_payload["to"] = req.to_timestamp
            try:
                search_resp = await adapter.datasets_search(
                    DatasetsSearchRequest.model_validate(search_payload)
                )
            except httpx.ReadTimeout as exc:
                err = ErrorResponse(
                    detail=(
                        f"Timeout connecting to Horreum MCP: {exc}. "
                        "This usually means the query took longer than the "
                        "configured timeout_seconds. Consider increasing "
                        "timeout_seconds in the config.json (current timeout "
                        "may be too low for complex queries with auto-discovery). "
                        "Recommended: 300s for complex queries."
                    ),
                    error_type="timeout",
                    available_options=None,
                )
                logger.warning(
                    "upstream.timeout",
                    extra={"req_id": get_request_id(), "phase": "datasets.search"},
                )
                raise http_exc(status_code=504, detail=err.model_dump()) from exc
            except httpx.ConnectError as exc:
                err = ErrorResponse(
                    detail=str(exc), error_type="network_error", available_options=None
                )
                logger.error(
                    "upstream.connect_error",
                    extra={"req_id": get_request_id(), "phase": "datasets.search"},
                )
                raise http_exc(status_code=504, detail=err.model_dump()) from exc
            except httpx.HTTPStatusError as exc:
                upstream = exc.response.status_code if exc.response else None
                body_preview = ""
                try:
                    if exc.response is not None:
                        txt = exc.response.text
                        if txt:
                            body_preview = txt if len(txt) <= 500 else txt[:500] + "..."
                except Exception:
                    body_preview = "(unavailable)"
                err = ErrorResponse(
                    detail=f"Upstream error {upstream}",
                    error_type="upstream_http_error",
                    available_options=None,
                )
                logger.error(
                    "upstream.http_status",
                    extra={
                        "req_id": get_request_id(),
                        "phase": "datasets.search",
                        "status": upstream,
                        "body_preview": body_preview,
                    },
                )
                raise http_exc(status_code=502, detail=err.model_dump()) from exc
            except httpx.HTTPError as exc:
                err = ErrorResponse(
                    detail=str(exc), error_type="upstream_error", available_options=None
                )
                logger.error(
                    "upstream.http_error",
                    extra={"req_id": get_request_id(), "phase": "datasets.search"},
                )
                raise http_exc(status_code=502, detail=err.model_dump()) from exc
            dataset_bodies = []
            for ds in search_resp.datasets[: req.limit]:
                try:
                    resp = await adapter.datasets_get(
                        DatasetsGetRequest.model_validate(
                            {
                                "dataset_id": ds.dataset_id,
                                "if_none_match": None,
                                "if_modified_since": None,
                            }
                        )
                    )
                except httpx.ReadTimeout as exc:
                    err = ErrorResponse(
                        detail=(
                            f"Timeout fetching datasets from Horreum MCP: {exc}. "
                            "Query exceeded configured timeout_seconds. "
                            "For complex queries with auto-discovery, increase "
                            "timeout_seconds in config.json to 300s or higher."
                        ),
                        error_type="timeout",
                        available_options=None,
                    )
                    logger.warning(
                        "upstream.timeout",
                        extra={
                            "req_id": get_request_id(),
                            "phase": "datasets.get",
                            "dataset_id": ds.dataset_id,
                        },
                    )
                    raise http_exc(status_code=504, detail=err.model_dump()) from exc
                except httpx.ConnectError as exc:
                    err = ErrorResponse(
                        detail=str(exc),
                        error_type="network_error",
                        available_options=None,
                    )
                    logger.error(
                        "upstream.connect_error",
                        extra={
                            "req_id": get_request_id(),
                            "phase": "datasets.get",
                            "dataset_id": ds.dataset_id,
                        },
                    )
                    raise http_exc(status_code=504, detail=err.model_dump()) from exc
                except httpx.HTTPStatusError as exc:
                    upstream = exc.response.status_code if exc.response else None
                    body_preview = ""
                    try:
                        if exc.response is not None:
                            txt = exc.response.text
                            if txt:
                                body_preview = (
                                    txt if len(txt) <= 500 else txt[:500] + "..."
                                )
                    except Exception:
                        body_preview = "(unavailable)"
                    err = ErrorResponse(
                        detail=f"Upstream error {upstream}",
                        error_type="upstream_http_error",
                        available_options=None,
                    )
                    logger.error(
                        "upstream.http_status",
                        extra={
                            "req_id": get_request_id(),
                            "phase": "datasets.get",
                            "dataset_id": ds.dataset_id,
                            "status": upstream,
                            "body_preview": body_preview,
                        },
                    )
                    raise http_exc(status_code=502, detail=err.model_dump()) from exc
                except httpx.HTTPError as exc:
                    err = ErrorResponse(
                        detail=str(exc),
                        error_type="upstream_error",
                        available_options=None,
                    )
                    logger.error(
                        "upstream.http_error",
                        extra={
                            "req_id": get_request_id(),
                            "phase": "datasets.get",
                            "dataset_id": ds.dataset_id,
                        },
                    )
                    raise http_exc(status_code=502, detail=err.model_dump()) from exc
                if isinstance(resp.content, dict):
                    dataset_bodies.append(resp.content)
                elif isinstance(resp.content, list):
                    # Horreum returns content as a list; extract each item
                    for item in resp.content:
                        if isinstance(item, dict):
                            dataset_bodies.append(item)

        try:
            points = await server.get_key_metrics_raw(
                req.dataset_types,
                cast(List[object], dataset_bodies),
                os_filter=os_filter_hint,
                run_type_filter=run_type_hint,
            )
        except KeyError as exc:
            # Unknown plugin id / dataset type
            available = [p.id for p in all_plugins()]
            err = ErrorResponse(
                detail=str(exc),
                error_type="unknown_dataset_type",
                available_options=available or None,
            )
            raise http_exc(status_code=400, detail=err.model_dump()) from exc
        query_duration = time.time() - query_start

        # Log memory usage after query completes
        mem_after_mb = None
        try:
            process = psutil.Process()
            mem_after = process.memory_info()
            mem_after_mb = round(mem_after.rss / 1024 / 1024, 1)
        except (ImportError, RuntimeError):  # pragma: no cover
            pass

        logger.info(
            "query.complete",
            extra={
                "req_id": get_request_id(),
                "duration_sec": round(query_duration, 2),
                "points": len(points),
                "path": "datasets",
                "memory_mb": mem_after_mb,
            },
        )
        logger.info(
            "http.get_key_metrics.success",
            extra={
                "req_id": get_request_id(),
                "points": len(points),
                "dataset_types": req.dataset_types,
            },
        )
        return GetKeyMetricsResponse(
            metric_points=[
                (p.model_dump() if hasattr(p, "model_dump") else p) for p in points
            ],
            domain_model_version="1.0.0",
        )

    @app.post(
        "/tools/get_key_metrics_raw",
        operation_id="get_key_metrics_raw",
        response_model=GetKeyMetricsResponse,
        dependencies=[depends(auth_dep)],
        tags=["mcp-tools"],
        summary="Analyze key metrics from client-provided raw dataset JSON",
        description=(
            "Process and extract key performance indicators from raw dataset "
            "objects provided directly by the client, without fetching from "
            "external sources."
        ),
        responses={
            400: {"model": ErrorResponse},
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            500: {"model": ErrorResponse},
        },
    )
    async def get_key_metrics_raw_http(
        req: GetKeyMetricsRequest,
    ) -> GetKeyMetricsResponse:
        # Extract filter hints from normalization (if os_id provided)
        # For raw mode, filters are passed via parameters, not auto-detected
        os_filter_hint = getattr(req, "os_id", None)
        run_type_hint = None  # Raw mode doesn't auto-detect run types

        dataset_bodies = req.data or []
        try:
            points = await server.get_key_metrics_raw(
                req.dataset_types,
                cast(List[object], dataset_bodies),
                os_filter=os_filter_hint,
                run_type_filter=run_type_hint,
            )
        except KeyError as exc:
            available = [p.id for p in all_plugins()]
            err = ErrorResponse(
                detail=str(exc),
                error_type="unknown_dataset_type",
                available_options=available or None,
            )
            raise http_exc(status_code=400, detail=err.model_dump()) from exc
        logger.info(
            "http.get_key_metrics_raw.success",
            extra={
                "points": len(points),
                "dataset_types": req.dataset_types,
                "datasets": len(dataset_bodies),
            },
        )
        return GetKeyMetricsResponse(
            metric_points=[
                (p.model_dump() if hasattr(p, "model_dump") else p) for p in points
            ],
            domain_model_version="1.0.0",
        )


# NOTE: The _register_mcp_over_http() function was removed because it created a
# custom /mcp POST endpoint that conflicted with the fastapi-mcp library's SSE
# endpoint at the same path. The fastapi-mcp library (mounted below at lines
# ~1055-1072) automatically handles the MCP protocol (initialize, tools/list,
# tools/call) by discovering FastAPI endpoints tagged with "mcp-tools" and having
# an operation_id set. It provides both SSE at /mcp and HTTP at /mcp/http without
# requiring custom endpoint registration.


def _register_query(
    app: Any,
    server: DomainMCPServer,
    depends: Any,
    http_exc: Any,
    auth_dep: Any,
) -> None:
    """Register natural language query endpoint (Phase 6.1).

    Provides LLM-powered natural language query capability via /api/query endpoint.
    Feature is optional and gracefully disabled if LLM is not configured.
    """
    # Lazy import LLM modules to avoid requiring dependencies if not used
    try:
        from ..llm.client import create_llm_client  # noqa: PLC0415
        from ..llm.orchestrator import create_orchestrator  # noqa: PLC0415
        from .rate_limiter import RateLimitConfig, RateLimiter  # noqa: PLC0415
    except ImportError as e:
        logger.info(
            "LLM modules not available, /api/query endpoint disabled",
            extra={"error": str(e)},
        )
        return

    # Load environment settings and check if LLM is configured
    settings = EnvSettings()  # type: ignore[call-arg]
    llm_client = create_llm_client(settings)

    # Initialize rate limiter (Phase 6.3)
    rate_limit_config = RateLimitConfig(
        requests_per_hour=getattr(settings, "RATE_LIMIT_REQUESTS_PER_HOUR", 100),
        tokens_per_hour=getattr(settings, "RATE_LIMIT_TOKENS_PER_HOUR", 100000),
        enable_rate_limiting=getattr(settings, "RATE_LIMIT_ENABLED", True),
        admin_bypass_key=getattr(settings, "RATE_LIMIT_ADMIN_KEY", None),
    )
    rate_limiter = RateLimiter(rate_limit_config)

    if not llm_client:
        logger.info(
            "/api/query endpoint disabled: LLM not configured",
            extra={"hint": "Set LLM_PROVIDER, LLM_API_KEY, and LLM_MODEL to enable"},
        )
        return

    # Create tool handlers dictionary for orchestrator
    # Map tool names to their async handler methods
    async def resources_read_handler(uri: str) -> Dict[str, Any]:
        """Handler for resources/read tool (MCP resource access)."""
        result = read_resource(uri)
        if result is None:
            raise ValueError(f"Resource not found: {uri}")
        return result

    # Create get_key_metrics wrapper that matches MCP-over-HTTP signature
    async def get_key_metrics_handler(**kwargs: Any) -> Dict[str, Any]:
        """Get boot time and performance metrics from configured sources.

        **PRIMARY TOOL** for boot time and performance analysis queries.

        Parameters
        ----------
        **For source-driven queries (recommended):**
        - run_id: Fetch metrics for a specific Horreum run ID (e.g., "123456")
          - When provided, fetches only that run (ignores time filters)
          - **Use this for "analyze run ID X" queries**
        - from_timestamp: Start time ("last 30 days", "2025-01-01", epoch millis)
        - to_timestamp: End time ("now", "yesterday", ISO timestamp)
        - os_id: Optional OS filter (e.g., "rhel", "autosd")
        - run_type: Filter by test run type ("nightly", "ci", "release", "manual")
        - limit: Page size (default 100), auto-paginates to fetch all results

        **DO NOT use these parameters** (they are auto-configured):
        - test_id (auto-discovered for boot time queries)
        - source_id (auto-selected)
        - dataset_types (defaults to ["boot-time-verbose"])

        Returns
        -------
        Dict[str, Any]
            Structured performance metrics with metric_points list and
            domain_model_version.
        """
        # Debug logging to capture LLM tool call parameters
        import json

        logger.info(f"llm.tool_call.get_key_metrics PARAMETERS: {json.dumps(kwargs)}")
        return await _call_get_key_metrics(server, kwargs)

    tool_handlers = {
        "get_key_metrics": get_key_metrics_handler,
        "resources/read": resources_read_handler,
    }

    # Create orchestrator
    orchestrator = create_orchestrator(
        llm_client=llm_client,
        tool_handlers=tool_handlers,
        max_iterations=getattr(settings, "LLM_MAX_ITERATIONS", 10),
        temperature=getattr(settings, "LLM_TEMPERATURE", 0.1),
    )

    logger.info(
        "/api/query endpoint enabled",
        extra={
            "llm_provider": getattr(settings, "LLM_PROVIDER", None),
            "llm_model": getattr(settings, "LLM_MODEL", None),
            "max_iterations": getattr(settings, "LLM_MAX_ITERATIONS", 10),
            "temperature": getattr(settings, "LLM_TEMPERATURE", 0.1),
        },
    )

    @app.post(
        "/api/query",
        response_model=QueryResponse,
        dependencies=[depends(auth_dep)],
        tags=["natural-language"],
        summary="Natural language query endpoint (LLM-powered)",
        description=(
            "Submit a natural language question about RHIVOS/AutoSD performance "
            "data. The LLM will orchestrate appropriate tool calls and provide "
            "a formatted answer. Requires LLM configuration (LLM_PROVIDER, "
            "LLM_API_KEY, LLM_MODEL env vars)."
        ),
        responses={
            400: {"model": ErrorResponse},
            401: {"description": "Unauthorized"},
            403: {"description": "Forbidden"},
            429: {
                "model": ErrorResponse,
                "description": "Rate limited (LLM or server)",
            },
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse, "description": "LLM not configured"},
        },
    )
    async def api_query(req: QueryRequest, request: Request) -> QueryResponse:
        """Process a natural language query using LLM orchestration."""
        req_id = get_request_id()
        query = req.query.strip()

        # Input validation (Phase 6.3)
        if not query:
            raise http_exc(
                status_code=400,
                detail={"error": "Query cannot be empty"},
            )

        max_query_length = getattr(settings, "QUERY_MAX_LENGTH", 2000)
        if len(query) > max_query_length:
            raise http_exc(
                status_code=400,
                detail={
                    "error": "Query too long",
                    "max_length": max_query_length,
                    "actual_length": len(query),
                },
            )

        # Check for suspicious patterns (basic sanitization)
        suspicious_patterns = [
            "\\x00",  # null bytes
            "\x00",
            "IGNORE PREVIOUS",  # prompt injection
            "IGNORE ALL",
            "SYSTEM:",
            "</s>",  # model control tokens
            "<|endoftext|>",
        ]
        query_upper = query.upper()
        for pattern in suspicious_patterns:
            if pattern in query_upper:
                logger.warning(
                    "Suspicious query pattern detected",
                    extra={
                        "req_id": req_id,
                        "pattern": pattern,
                        "query_prefix": query[:100],
                    },
                )
                raise http_exc(
                    status_code=400,
                    detail={
                        "error": "Query contains suspicious patterns",
                        "message": (
                            "Please rephrase your query without "
                            "special control sequences"
                        ),
                    },
                )

        # Rate limiting check (Phase 6.3)
        client_id = request.client.host if request.client else "unknown"
        admin_key = req.admin_key if hasattr(req, "admin_key") else None

        allowed, error_msg = rate_limiter.check_rate_limit(client_id, admin_key)
        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "req_id": req_id,
                    "client_id": client_id,
                    "error": error_msg,
                },
            )
            raise http_exc(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": error_msg,
                },
            )

        logger.info(
            "api.query.start",
            extra={
                "req_id": req_id,
                "client_id": client_id,
                "query": query[:100],  # Log first 100 chars
                "query_length": len(query),
            },
        )

        try:
            # Execute query via orchestrator
            result = await orchestrator.execute_query(query)

            # Record request and token usage (Phase 6.3)
            rate_limiter.record_request(client_id, result.total_tokens)

            # Get rate limit stats (Phase 6.3)
            rate_stats = rate_limiter.get_client_stats(client_id)

            logger.info(
                "api.query.complete",
                extra={
                    "req_id": req_id,
                    "client_id": client_id,
                    "tool_calls": len(result.tool_calls),
                    "llm_calls": result.llm_calls,
                    "duration_ms": result.total_duration_ms,
                    "total_tokens": result.total_tokens,
                    "tokens_remaining": rate_stats["tokens_remaining"],
                },
            )

            return QueryResponse(
                query=query,
                answer=result.answer,
                metadata={
                    "tool_calls": len(result.tool_calls),
                    "llm_calls": result.llm_calls,
                    "duration_ms": result.total_duration_ms,
                    "total_tokens": result.total_tokens,
                    "rate_limit": rate_stats,
                },
                tool_calls=result.tool_calls,
            )

        except Exception as e:
            logger.error(
                "api.query.failed",
                extra={
                    "req_id": req_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            # Check for rate limiting errors
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                raise http_exc(
                    status_code=429,
                    detail={
                        "error": "LLM API rate limit exceeded",
                        "message": str(e),
                    },
                ) from e
            # Generic error
            raise http_exc(
                status_code=500,
                detail={
                    "error": "Query processing failed",
                    "message": str(e),
                },
            ) from e


def create_app():
    """Create and configure the FastAPI application.

    The HTTP layer is intentionally thin and defers to shared tool handlers
    and normalization. Imports are loaded dynamically to avoid forcing
    FastAPI/uvicorn presence in environments that only use stdio.
    """
    settings = EnvSettings()
    # Respect prior logging configuration from CLI; otherwise use env setting
    if not logging.getLogger().hasHandlers():
        setup_logging(settings.log_level)
    parts = _load_fastapi()
    server = DomainMCPServer()

    @asynccontextmanager
    async def lifespan(_app: Any):
        logger.info("http.startup")

        # Log memory and resource information at startup
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            logger.info(
                "http.startup.memory",
                extra={
                    "rss_mb": round(mem_info.rss / 1024 / 1024, 1),
                    "vms_mb": round(mem_info.vms / 1024 / 1024, 1),
                },
            )
            # Detect container memory limit if available
            cgroup_limit = None
            try:
                with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
                    cgroup_limit = int(f.read().strip())
                    if cgroup_limit < (1 << 60):  # Filter out "unlimited" values
                        logger.info(
                            "http.startup.container_memory_limit",
                            extra={"limit_mb": round(cgroup_limit / 1024 / 1024, 1)},
                        )
            except (FileNotFoundError, ValueError, PermissionError):
                # Try cgroups v2
                try:
                    with open("/sys/fs/cgroup/memory.max") as f:
                        cgroup_str = f.read().strip()
                        if cgroup_str != "max":
                            cgroup_limit = int(cgroup_str)
                            logger.info(
                                "http.startup.container_memory_limit",
                                extra={
                                    "limit_mb": round(cgroup_limit / 1024 / 1024, 1)
                                },
                            )
                except (FileNotFoundError, ValueError, PermissionError):
                    pass
        except (ImportError, RuntimeError):  # pragma: no cover
            pass

        # Reset plugin registry per app instance to avoid cross-test/runtime leakage
        try:
            reset_plugins()
        except (
            ImportError,
            RuntimeError,
            AttributeError,
            ValueError,
        ):  # pragma: no cover - defensive
            logger.debug("plugins.reset failed; continuing with current registry")

        # Initialize MCP Resources registry at startup
        try:
            from .resources import get_registry

            registry = get_registry()
            logger.info(f"Loaded {len(registry.resources)} MCP resources")
        except Exception as exc:
            logger.warning(f"Failed to load MCP resources: {exc}")

        await server.start()
        try:
            # Startup connection diagnostics for configured adapters
            connections: List[Dict[str, Any]] = []
            for sid in get_available_source_ids():
                status: Dict[str, Any] = {"source_id": sid, "ok": False}
                try:
                    adapter = get_adapter(sid)
                    # Lightweight contract call; patched in tests to avoid network
                    await adapter.tests_list(
                        TestsListRequest.model_validate({"page_size": 1})
                    )
                    status["ok"] = True
                    # Attempt MCP session initialization if available on adapter
                    has_session = False
                    init = getattr(adapter, "init_session", None)
                    if callable(init):
                        sid_val = await init()  # type: ignore[misc]
                        has_session = bool(sid_val)
                    status["has_session"] = has_session
                except (
                    KeyError,
                    ValidationError,
                    httpx.HTTPError,
                    OSError,
                    asyncio.TimeoutError,
                    ValueError,
                ) as exc:
                    status["error"] = str(exc)
                connections.append(status)
            if connections:
                logger.info(
                    "http.startup.connections", extra={"connections": connections}
                )
            yield
        finally:
            logger.info("http.shutdown")
            await server.stop()

    app = _build_app(parts["fastapi_cls"], lifespan=lifespan)
    # Global exception handlers to ensure structured error responses
    # Access request class to satisfy linters and for potential future use
    request_validation_error_cls = parts["validation_exc"]
    jr = parts["json_response"]
    starlette_http_exception_cls = parts["starlette_http_exc"]

    @app.exception_handler(request_validation_error_cls)
    async def validation_exception_handler(_request: Any, exc: Exception):  # noqa: D401
        err = ErrorResponse(
            detail=str(exc), error_type="validation_error", available_options=None
        )
        return jr(status_code=400, content={"detail": err.model_dump()})

    @app.exception_handler(starlette_http_exception_cls)
    async def http_exception_handler(_request: Any, exc: Any):  # noqa: D401
        # Pass through existing HTTP errors but ensure structured payload
        detail = getattr(exc, "detail", "")
        if isinstance(detail, dict) and {"detail", "error_type"} <= detail.keys():
            payload = {"detail": detail}
        else:
            payload = ErrorResponse(
                detail=str(detail) or "HTTP error",
                error_type="http_error",
                available_options=None,
            ).model_dump()
            payload = {"detail": payload}
        return jr(status_code=exc.status_code, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Any, exc: Exception):  # noqa: D401
        # Avoid leaking internals; log server-side, return generic error
        logger.error("http.unhandled_exception", exc_info=exc)
        err = ErrorResponse(
            detail="Internal error. See server logs for request id.",
            error_type="internal_server_error",
            available_options=None,
        )
        return jr(status_code=500, content={"detail": err.model_dump()})

    # Mark handlers as intentionally used (registered via decorators)
    _ = (
        validation_exception_handler,
        http_exception_handler,
        unhandled_exception_handler,
    )

    _apply_cors_env(app, parts["cors_mw"])
    auth_dep = _make_auth_dependency(
        parts["header"], parts["http_exc"], parts["status"]
    )
    _register_health(app)
    _register_capabilities(app)
    _register_resources(app)
    _register_debug(app)
    _register_tools(
        app,
        server,
        parts["depends"],
        parts["http_exc"],
        auth_dep,
        parts.get("body"),
    )
    _register_query(
        app,
        server,
        parts["depends"],
        parts["http_exc"],
        auth_dep,
    )
    # NOTE: _register_mcp_over_http() call removed - the fastapi-mcp library
    # (mounted below at lines ~1360-1377) automatically handles MCP protocol
    # (initialize, tools/list, tools/call) by discovering FastAPI endpoints
    # with operation_id set. The custom /mcp endpoint was conflicting with
    # fastapi-mcp's SSE endpoint and causing auth issues.
    # Optional: extend PYTHONPATH for container plugin discovery
    extra_pp = os.environ.get("DOMAIN_MCP_EXTRA_PYTHONPATH", "")
    added_paths: List[str] = []
    if extra_pp:
        for part in [p.strip() for p in extra_pp.split(":") if p.strip()]:
            if part not in sys.path:
                sys.path.append(part)
                added_paths.append(part)
    if added_paths:
        logger.info("pythonpath.update", extra={"added": added_paths})

    # Configuration discovery and adapter initialization
    cfg_env = os.environ.get("DOMAIN_MCP_CONFIG")
    cfg_path = Path(cfg_env) if cfg_env else None
    cfg_found = cfg_path is not None and cfg_path.exists()
    adapters_initialized: List[str] = []
    config_error: str | None = None
    if cfg_found and cfg_path is not None:
        try:
            cfg = AppConfig.load(cfg_path)
            for source_id, sc in cfg.sources.items():
                if sc.type in ("horreum", "horreum-mcp-http", "http"):
                    register_adapter(
                        source_id,
                        HorreumAdapter(
                            sc.endpoint,
                            sc.api_key,
                            sc.timeout_seconds,
                            max_retries=sc.max_retries,
                            backoff_initial_ms=sc.backoff_initial_ms,
                            backoff_multiplier=sc.backoff_multiplier,
                        ),
                    )
                    adapters_initialized.append(f"{source_id}:http")
                elif sc.type in ("horreum-stdio", "horreum-mcp-stdio", "stdio"):
                    register_adapter(
                        source_id,
                        MCPBridgeAdapter(
                            command=sc.endpoint,
                            args=sc.stdio_args or [],
                            timeout=sc.timeout_seconds,
                            env=sc.env or {},
                        ),
                    )
                    adapters_initialized.append(f"{source_id}:stdio")
        except (OSError, ValueError, ValidationError) as exc:  # config parse/load error
            config_error = str(exc)
    # Configuration visibility logging
    settings_dict: Dict[str, Any] = {
        "log_level": settings.log_level,
        "cors_origins": os.environ.get("DOMAIN_MCP_CORS_ORIGINS", ""),
        "http_auth": "enabled" if _get_expected_token() else "disabled",
        "config_path": str(cfg_path) if cfg_path else None,
        "config_found": cfg_found,
        "config_error": config_error,
        "adapters_initialized": adapters_initialized,
    }
    logger.info("http.startup.settings", extra=settings_dict)
    # Container-oriented diagnostics (visibility only; avoids secrets)
    container_diag: Dict[str, Any] = {
        "env_has_token": bool(os.environ.get("DOMAIN_MCP_HTTP_TOKEN")),
        "env_has_config": bool(os.environ.get("DOMAIN_MCP_CONFIG")),
        "config_mount_exists": bool(cfg_found),
        "workdir": os.getcwd(),
        "pythonpath_env": os.environ.get("PYTHONPATH", ""),
        "config_readable": bool(
            cfg_found and cfg_path and os.access(cfg_path, os.R_OK)
        ),
        "sys_path_count": len(sys.path),
    }
    logger.info("http.startup.container", extra=container_diag)

    # If a config path is provided but not readable, emit a clear hint for containers
    if cfg_found and cfg_path is not None and not os.access(cfg_path, os.R_OK):
        logger.info(
            "http.startup.config_unreadable",
            extra={
                "config_path": str(cfg_path),
                "suggestion": (
                    "Ensure volume is mounted readably (e.g., add :Z on Podman/SELinux)"
                ),
            },
        )

    # High-level container operational status derived from visibility signals
    container_status: Dict[str, Any] = {
        "configured": cfg_found,
        "has_token": bool(os.environ.get("DOMAIN_MCP_HTTP_TOKEN")),
        "adapters_ready": bool(adapters_initialized),
        "source_driven_available": bool(get_available_source_ids()),
        "raw_mode_available": True,
    }
    logger.info("http.startup.container_status", extra=container_status)

    # Guidance for missing/invalid configuration with actionable help
    if not cfg_found:
        logger.info(
            "http.startup.guidance",
            extra={
                "problem": "config_not_found",
                "example_config_env": "export DOMAIN_MCP_CONFIG=/etc/mcp/config.json",
                "example_volume_mount": (
                    "-v /host/config.json:/etc/mcp/config.json:ro"
                ),
                "raw_mode_hint": True,
                "docs": "https://github.com/dustinblack/horreum-mcp",
            },
        )
    if config_error:
        logger.info(
            "http.startup.config_error",
            extra={
                "config_path": str(cfg_path) if cfg_path else None,
                "error": config_error,
                "suggestion": (
                    "Validate JSON format and required fields. See README 'HTTP "
                    "mode configuration' and ensure containers mount the file."
                ),
            },
        )

    # Apply plugin enable/disable filtering from config, if present
    if cfg_found and cfg_path is not None:
        try:
            cfg = AppConfig.load(cfg_path)
            if cfg.enabled_plugins:
                result = apply_enabled_plugins(cfg.enabled_plugins)
                logger.info("plugins.enabled", extra=result)
        except (OSError, ValueError, ValidationError):
            pass

    # Capabilities summary snapshot for logs (mirrors /capabilities response)
    try:
        token = _get_expected_token()
        cors = os.environ.get("DOMAIN_MCP_CORS_ORIGINS", "")
        cors_list = [o.strip() for o in cors.split(",") if o.strip()]
        source_ids = get_available_source_ids()
        tools_list = ["get_key_metrics", "get_key_metrics_raw"]
        plugins_list = [p.id for p in all_plugins()]
        logger.info(
            "http.startup.capabilities",
            extra={
                "http_auth": ("enabled" if token else "disabled"),
                "cors_origins": cors_list,
                "modes": {"raw": True, "source_driven": bool(source_ids)},
                "tools": tools_list,
                "plugins": plugins_list,
                "sources": source_ids,
            },
        )
        # Detailed adapters snapshot (ids and types)
        adapters_detail: List[Dict[str, str]] = []
        for sid in get_available_source_ids():
            try:
                adapters_detail.append(
                    {"id": sid, "type": type(get_adapter(sid)).__name__}
                )
            except KeyError:
                continue
        if adapters_detail:
            logger.info(
                "http.startup.adapters_detail", extra={"adapters": adapters_detail}
            )
        # Adapter telemetry snapshot (retry/backoff if available)
        telemetry: List[Dict[str, Any]] = []
        for sid in get_available_source_ids():
            try:
                adapter = get_adapter(sid)
            except KeyError:
                continue
            # Only include known attributes to avoid leaking sensitive info
            attrs: Dict[str, Any] = {"id": sid, "type": type(adapter).__name__}
            for attr in (
                "_max_retries",
                "_backoff_initial_ms",
                "_backoff_multiplier",
            ):
                if hasattr(adapter, attr):
                    attrs[attr.removeprefix("_")] = getattr(adapter, attr)
            telemetry.append(attrs)
        if telemetry:
            logger.info(
                "http.startup.adapter_telemetry", extra={"telemetry": telemetry}
            )
        # Consolidated summary combining settings, capabilities and adapters
        logger.info(
            "http.startup.summary",
            extra={
                "http_auth": ("enabled" if _get_expected_token() else "disabled"),
                "cors_origins": os.environ.get("DOMAIN_MCP_CORS_ORIGINS", ""),
                "config_path": str(cfg_path) if cfg_path else None,
                "config_found": cfg_found,
                "modes": {"raw": True, "source_driven": bool(source_ids)},
                "tools": tools_list,
                "plugins": plugins_list,
                "sources": adapters_initialized or source_ids,
            },
        )
    except (RuntimeError, OSError, ValueError):  # pragma: no cover - defensive
        pass
    log_plugin_status()
    log_plugin_discovery_debug()
    log_adapter_status()

    # Note: MCPRequestLoggingMiddleware disabled due to incompatibility with
    # SSE streaming. BaseHTTPMiddleware breaks ASGI streaming protocol.
    # TODO: Implement raw ASGI middleware for MCP request logging if needed.
    # The MCP library loggers (enabled in observability/__init__.py) provide
    # protocol-level visibility without breaking streaming.

    # Mount MCP server using fastapi-mcp library
    # Support both SSE (for Gemini CLI) and HTTP (for Claude Desktop, curl, etc.)
    if FastApiMCP is not None:
        mcp = FastApiMCP(
            app,
            name="domain-mcp-server",
            description="Domain MCP for analyzing performance datasets from Horreum",
            include_tags=["mcp-tools"],
        )
        # Note: We don't register custom list_tools() or call_tool() handlers
        # because fastapi-mcp automatically handles these by discovering FastAPI
        # endpoints tagged with "mcp-tools". Our middleware logs all MCP requests.

        # Mount SSE transport at /mcp
        mcp.mount_sse(mount_path="/mcp")
        logger.info(
            "http.mcp.sse.mounted",
            extra={"path": "/mcp", "transport": "sse", "clients": "Gemini CLI"},
        )
        # Mount HTTP transport at /mcp/http
        mcp.mount_http(mount_path="/mcp/http")
        logger.info(
            "http.mcp.http.mounted",
            extra={
                "path": "/mcp/http",
                "transport": "http",
                "clients": "Claude Desktop, curl",
            },
        )
    else:
        logger.warning("fastapi-mcp not available; MCP endpoints not mounted")

    return app


def _get_expected_token() -> str | None:
    """Return expected bearer token from environment, or ``None`` if disabled.

    Environment variable: ``DOMAIN_MCP_HTTP_TOKEN``.
    """
    token = os.environ.get("DOMAIN_MCP_HTTP_TOKEN")
    return token if token else None
