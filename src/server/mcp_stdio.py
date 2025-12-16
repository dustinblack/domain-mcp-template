"""Minimal MCP stdio server to enable AI chat client integration (experimental).

This module exposes a very small Model Context Protocol (MCP) server over
stdio so MCP-capable AI chat clients can connect and invoke the Domain MCP
tools. For now, only a raw-mode `get_key_metrics_raw` tool is registered to
exercise end-to-end integration.

The implementation uses the Python MCP SDK if available. To run, install the
package providing MCP server primitives (package name may be `mcp`). If the
SDK is not installed, a clear error is raised at runtime.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import signal
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from .. import __domain_model_version__
from ..adapters import (
    get_adapter,
    get_available_source_ids,
    log_adapter_status,
    register_adapter,
)
from ..adapters.horreum import HorreumAdapter
from ..adapters.mcp_bridge import MCPBridgeAdapter
from ..config.models import AppConfig
from ..domain.plugins import log_plugin_status
from ..observability import setup_logging
from ..schemas.source_mcp_contract import (
    DatasetsGetRequest,
    DatasetsSearchRequest,
    TestsListRequest,
)
from .app import DomainMCPServer
from .models import (
    FetchPlanStep,
    GetKeyMetricsPlanResponse,
    GetKeyMetricsRequest,
    GetKeyMetricsResponse,
)
from .normalize import normalize_get_key_metrics_params
from .resources import read_resource

logger = logging.getLogger(__name__)


def _load_mcp_sdk() -> tuple[Optional[Any], Optional[Any]]:
    """Load FastMCP class and stdio context manager if available."""
    try:
        fast_mod = importlib.import_module("mcp.server.fastmcp")
        stdio_mod = importlib.import_module("mcp.server.stdio")
        return getattr(fast_mod, "FastMCP"), getattr(stdio_mod, "stdio_server")
    except (ImportError, ModuleNotFoundError):  # pragma: no cover
        return None, None


def _init_adapters_from_env() -> None:
    """Load adapters from DOMAIN_MCP_CONFIG if set.

    Reads the JSON config via ``AppConfig`` and registers source adapters
    (currently Horreum HTTP) under their ``source_id`` for use by
    source-driven tools.
    """
    config_path = os.environ.get("DOMAIN_MCP_CONFIG")
    if not config_path:
        log_adapter_status()
        return
    cfg = AppConfig.load(Path(config_path))
    for source_id, sc in cfg.sources.items():
        if sc.type in ("horreum", "horreum-mcp-http", "http"):
            register_adapter(
                source_id, HorreumAdapter(sc.endpoint, sc.api_key, sc.timeout_seconds)
            )
        elif sc.type in ("horreum-stdio", "horreum-mcp-stdio", "stdio"):
            register_adapter(
                source_id,
                MCPBridgeAdapter(
                    command=sc.endpoint,
                    args=sc.stdio_args or [],
                    timeout=sc.timeout_seconds,
                ),
            )
    log_adapter_status()


def _normalize_get_key_metrics_params(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Delegate to shared normalization utilities."""
    return normalize_get_key_metrics_params(raw)


def _register_tools(mcp_app: Any, app: DomainMCPServer) -> None:
    """Register MCP tools on the FastMCP app.

    Registers:
    - ping: simple health-check tool
    - get_key_metrics_raw: raw-mode extraction from client-provided datasets
    - get_key_metrics: source-driven extraction using configured adapters
    """
    tool_dec = getattr(mcp_app, "tool", None)
    if tool_dec is None:
        raise RuntimeError(
            "MCP SDK version lacks FastMCP.tool(); try: pip install -U mcp"
        )

    @tool_dec(name="ping")
    async def ping() -> str:
        return "ok"

    @tool_dec(name="get_key_metrics_raw")
    async def get_key_metrics_raw_tool(params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance metrics from raw dataset JSON.

        Use this tool when you have raw performance test data (JSON datasets)
        and need to extract key metrics like boot times, throughput, latency, etc.
        Supports boot-time analysis, performance benchmarks, and system metrics.

        Parameters
        ----------
        params: Dict[str, Any]
            Object with keys:
            - dataset_types: List of metric types (e.g., ["boot-time-verbose"])
            - data: List of raw JSON dataset objects from performance tests

        Returns
        -------
        Dict[str, Any]
            Structured metrics ready for analysis, tables, or visualization.
        """
        dataset_types = cast(List[str], params.get("dataset_types", []))
        data = cast(List[Dict[str, Any]], params.get("data", []))
        os_filter = params.get("os_id") or params.get("os_filter")
        run_type_filter = params.get("run_type_filter")
        points = await app.get_key_metrics_raw(
            dataset_types,
            cast(List[object], data),
            os_filter=os_filter,
            run_type_filter=run_type_filter,
        )

        def _to_jsonable(obj: Any) -> Any:
            model_dump = getattr(obj, "model_dump", None)
            return model_dump() if callable(model_dump) else obj

        metric_points = [_to_jsonable(x) for x in points]
        return {"metric_points": metric_points, "domain_model_version": "1.0.0"}

    @tool_dec(name="get_key_metrics")
    async def get_key_metrics_tool(params: Dict[str, Any]) -> Dict[str, Any]:
        """Get boot time and performance metrics from configured sources.

        **PRIMARY TOOL** for boot time and performance analysis queries.

        **AUTO-CONFIGURATION** (all parameters optional):
        • source_id → first available source
        • dataset_types → ["boot-time-verbose"]
        • test_id → auto-discovers boot time tests
        • limit → page size (100), server paginates ALL results

        **CRITICAL CONSTRAINTS:**
        🚫 NEVER use test_id for boot time queries (auto-discovery works)
        🚫 OS identifiers (rhel, autosd, rhivos) are LABELS not test IDs
        🚫 Platform names (qemu, intel-nuc) are LABELS not test IDs
        ✅ Statistical calculations: server-side ONLY (deterministic)
        ✅ Results organized by: target × mode × os_id (3D matrix)

        **COMMON QUERY PATTERNS:**
        • "Boot times last 30 days" → {from_timestamp: "last 30 days"}
        • "RHEL boot performance" → {os_id: "rhel"}
        • "Nightly runs last week" → {from_timestamp: "last week"}
        • "Show statistics" → Returns all 7 statistical metrics

        **DEFAULT RETURNS:**
        Boot Phases: kernel_pre_timer, kernel, initrd, switchroot, system_init
        Total: Sum of phases (missing = 0, noted in missing_phases dimension)
        KPIs: early_service, start_kmod_load, first_service, network_online
        Statistics (when requested): min, mean, max, p95, p99, std_dev, CV

        **RESULT STRUCTURE:**
        Each metric_point contains:
        • metric_id: phase/total/KPI identifier
        • timestamp: test execution time
        • value: measurement (milliseconds)
        • dimensions: {os_id, mode, target} for 3D grouping
        • source: data origin (label_values or dataset)

        **3D MATRIX ORGANIZATION** (REQUIRED):
        Group results by dimensions fields:
        1. target: Platform (qemu, intel-nuc, raspberry-pi, orin, ridesx4,
           j784s4, rcar-s4)
        2. mode: Image type (package, container, OSTree)
        3. os_id: OS variant (rhel, autosd, fedora)

        This enables: platform comparison, mode comparison, OS comparison

        **REPORT METADATA** (required for reports):
        All available in dimensions: os_id, mode, target, release, image_name,
        samples, user, build
        From timestamp: start time
        Note: All metadata now available on fast path (no dataset query needed)

        **FILTERING:**
        OS: Pass as os_id parameter (rhivos → rhel auto-normalized)
        Platform: Extract from dimensions.target after query
        Run Type: Detected from query context (nightly, ci, release, manual)

        **MCP RESOURCES** (domain knowledge reference):
        - domain://examples/boot-time-report-template - WHAT TO INCLUDE (READ FIRST)
        - domain://examples/3d-matrix-organization - HOW TO organize results
        - domain://glossary/boot-time - Boot time domain reference
        - domain://glossary/metadata-fields - Required metadata fields
        - domain://examples/statistical-analysis - Statistics guide
        - domain://examples/boot-time-basic - Basic query patterns
        - domain://examples/filter-by-os - OS filtering examples

        See docs/domain-glossary.md § Boot Time Domain for complete reference

        Parameters
        ----------
        params: Dict[str, Any]
            **For source-driven queries (recommended):**
            - source_id: "horreum-stdio" (or configured source, auto-selected)
            - dataset_types: ["boot-time-verbose"] (["performance"], auto-config)
            - test_id: Optional test name/ID filter (auto-discovered if omitted)
            - limit: Page size (default 100), auto-paginates to fetch all results
            - from_timestamp: Start ("last 30 days", "2025-01-01", epoch millis)
            - to_timestamp: End time ("now", "yesterday", ISO timestamp)

            **For raw data processing:**
            - data: List of raw JSON dataset objects
            - dataset_types: List of metric types to extract

            **Natural language support:** Accepts "boot time", "horreum", etc.

        Returns
        -------
        Dict[str, Any]
            Structured performance metrics with the following format:
            {
              "metric_points": [
                {
                  "metric_id": "boot.time.total_ms",
                  "timestamp": "2025-10-07T12:34:56.789Z",
                  "value": 8543.2,
                  "unit": "ms",
                  "dimensions": {"os_id": "rhel", "mode": "production"},
                  "source": "boot-time-verbose"
                }
              ],
              "domain_model_version": "1.0.0"
            }

            Each metric_point represents a single test execution ("run") with:
            - metric_id: The specific KPI measured
            - timestamp: When the test was executed
            - value: The measured value
            - unit: Unit of measurement
            - dimensions: Dict with os_id, mode, target for 3D grouping
            - source: Run/dataset IDs for traceability

            For boot time queries, each metric_point typically represents one
            boot measurement from a test run.
        """
        # Normalize and validate input using shared request model
        normalized = _normalize_get_key_metrics_params(params)
        # Extract filter hints before Pydantic validation strips them
        os_filter_hint = normalized.pop("_detected_os_filter", None)
        run_type_hint = normalized.pop("_detected_run_type", None)
        req = GetKeyMetricsRequest.model_validate(normalized)

        # Plan-only mode: return client-executable plan and exit early
        if req.plan_only:
            plan = app.build_horreum_fetch_plan(
                test_id=req.test_id, schema_uri=req.schema_uri, limit=req.limit
            )
            return GetKeyMetricsPlanResponse(
                fetch_plan=[FetchPlanStep.model_validate(s) for s in plan],
                domain_model_version=__domain_model_version__,
            ).model_dump()

        dataset_bodies: List[Dict[str, Any]]
        if req.data is not None:
            # Raw mode
            dataset_bodies = cast(List[Dict[str, Any]], req.data)
        else:
            # Source-driven mode - auto-configure if not specified
            if not req.source_id:
                # Auto-select first available source
                available_sources = get_available_source_ids()
                if available_sources:
                    req.source_id = available_sources[0]
                    logger.info(f"Auto-selected source_id: {req.source_id}")
                else:
                    error_msg = (
                        "No Horreum MCP server connection configured. "
                        "Configure DOMAIN_MCP_CONFIG to enable source mode, "
                        "or provide 'data' for raw mode analysis."
                    )
                    return {
                        "error": error_msg,
                        "available_source_ids": [],
                        "domain_model_version": "1.0.0",
                    }

            # Auto-configure dataset_types if not provided
            if not req.dataset_types:
                req.dataset_types = ["boot-time-verbose"]
                logger.info("Auto-configured dataset_types: ['boot-time-verbose']")

            # Try to use a registered adapter; if not present, return helpful error
            try:
                adapter = get_adapter(req.source_id)

                # Auto-discover test_id if not provided (for boot-time queries)
                if not req.test_id and "boot-time" in str(req.dataset_types):
                    try:
                        # Try exact match first
                        tests_resp = await adapter.tests_list(
                            TestsListRequest(query="boot-time-verbose", page_size=10)
                        )
                        exact_match = [
                            t
                            for t in tests_resp.tests
                            if "boot-time-verbose" in t.name.lower()
                        ]
                        # Fallback to broader search
                        if not exact_match:
                            tests_resp = await adapter.tests_list(
                                TestsListRequest(query="boot", page_size=50)
                            )
                            exact_match = [
                                t
                                for t in tests_resp.tests
                                if "boot-time" in t.name.lower()
                                and "quarkus" not in t.name.lower()
                                and "spring" not in t.name.lower()
                            ]
                        if exact_match:
                            req.test_id = exact_match[0].test_id
                            logger.info(
                                f"Auto-discovered test: {exact_match[0].name} "
                                f"(test_id: {req.test_id})"
                            )
                    except Exception as e:
                        logger.warning(f"Could not auto-discover test: {e}")
            except KeyError:
                available = get_available_source_ids()
                if not available:
                    error_msg = (
                        "Cannot fetch data from external sources - no Horreum MCP "
                        "server connection configured. To analyze data from Horreum, "
                        "you need to configure an external MCP server connection. "
                        "For now, use raw mode by providing 'data' with your JSON "
                        "datasets instead of 'source_id'. "
                        "See: https://github.com/dustinblack/horreum-mcp"
                    )
                else:
                    error_msg = (
                        f"Source ID '{req.source_id}' not found. "
                        f"Available source IDs: {', '.join(available)}. "
                        f"Check your DOMAIN_MCP_CONFIG for correct source_id names."
                    )
                return {
                    "error": error_msg,
                    "available_source_ids": available,
                    "domain_model_version": "1.0.0",
                }
            search_payload: Dict[str, Any] = {
                "test_id": req.test_id,
                "schema_uri": req.schema_uri,
                "page_size": req.limit,
            }
            # Include time filters if caller supplied them (pass-through keys)
            if "from" in normalized:
                search_payload["from"] = normalized["from"]
            if "to" in normalized:
                search_payload["to"] = normalized["to"]

            dataset_bodies = []
            page_count = 0

            # Auto-paginate through all results
            while True:
                page_count += 1
                search_resp = await adapter.datasets_search(
                    DatasetsSearchRequest.model_validate(search_payload)
                )

                for ds in search_resp.datasets:
                    resp = await adapter.datasets_get(
                        DatasetsGetRequest.model_validate(
                            {
                                "dataset_id": ds.dataset_id,
                                "if_none_match": None,
                                "if_modified_since": None,
                            }
                        )
                    )
                    if isinstance(resp.content, dict):
                        dataset_bodies.append(resp.content)
                    elif isinstance(resp.content, list):
                        for item in resp.content:
                            if isinstance(item, dict):
                                dataset_bodies.append(item)

                # Check if there are more pages
                if not search_resp.pagination.has_more:
                    logger.info(
                        f"Fetched all datasets: {len(dataset_bodies)} total "
                        f"across {page_count} page(s)"
                    )
                    break

                # Get next page using pagination token
                if search_resp.pagination.next_page_token:
                    search_payload["page_token"] = (
                        search_resp.pagination.next_page_token
                    )
                else:
                    logger.warning(
                        "Pagination indicated has_more=True but no next_page_token"
                    )
                    break

        points = await app.get_key_metrics_raw(
            req.dataset_types,
            cast(List[object], dataset_bodies),
            os_filter=os_filter_hint,
            run_type_filter=run_type_hint,
        )

        return GetKeyMetricsResponse(
            metric_points=[
                (p.model_dump() if hasattr(p, "model_dump") else p) for p in points
            ],
            domain_model_version="1.0.0",
        ).model_dump()

    # Register resource handlers for domain knowledge exposure
    resource_dec = getattr(mcp_app, "resource", None)
    if resource_dec is not None:
        # MCP Resources available - register individual resource URIs

        @resource_dec(uri="domain://glossary/boot-time")
        async def boot_time_glossary() -> str:  # noqa: F841
            """Boot time domain knowledge resource."""
            result = read_resource("domain://glossary/boot-time")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://glossary/os-identifiers")
        async def os_identifiers_glossary() -> str:  # noqa: F841
            """OS identifier domain knowledge resource."""
            result = read_resource("domain://glossary/os-identifiers")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://glossary/platform-identifiers")
        async def platform_identifiers_glossary() -> str:  # noqa: F841
            """Platform identifier domain knowledge resource."""
            result = read_resource("domain://glossary/platform-identifiers")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://glossary/metadata-fields")
        async def metadata_fields_glossary() -> str:  # noqa: F841
            """Metadata fields domain knowledge resource."""
            result = read_resource("domain://glossary/metadata-fields")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://examples/boot-time-basic")
        async def boot_time_basic_example() -> str:  # noqa: F841
            """Basic boot time query example resource."""
            result = read_resource("domain://examples/boot-time-basic")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://examples/filter-by-os")
        async def filter_by_os_example() -> str:  # noqa: F841
            """Filter by OS query example resource."""
            result = read_resource("domain://examples/filter-by-os")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://examples/statistical-analysis")
        async def statistical_analysis_example() -> str:  # noqa: F841
            """Statistical analysis query example resource."""
            result = read_resource("domain://examples/statistical-analysis")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://examples/3d-matrix-organization")
        async def matrix_organization_example() -> str:  # noqa: F841
            """3D matrix result organization example resource."""
            result = read_resource("domain://examples/3d-matrix-organization")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        @resource_dec(uri="domain://examples/boot-time-report-template")
        async def boot_time_report_template() -> str:  # noqa: F841
            """Boot time report template resource (what to include)."""
            result = read_resource("domain://examples/boot-time-report-template")
            if result and "contents" in result:
                return result["contents"][0]["text"]
            return "{}"

        logger.info("MCP Resources registered: 9 domain knowledge resources")
    else:
        logger.warning(
            "MCP SDK version lacks resource support; "
            "upgrade with: pip install -U mcp"
        )

    # Mark as used for linters
    _ = (ping, get_key_metrics_raw_tool, get_key_metrics_tool)


async def _serve_forever(mcp_app: Any, app: DomainMCPServer) -> None:
    """Run FastMCP stdio server with graceful shutdown.

    Starts the stdio transport, prints user-facing startup/shutdown messages,
    and handles Ctrl-C (SIGINT) to exit cleanly without traceback.
    """
    logger.info("Starting MCP stdio server (attach your MCP client)...")
    shutdown_event = asyncio.Event()
    shutting_down = False

    def _on_sigint() -> None:
        nonlocal shutting_down
        if not shutting_down:
            shutting_down = True
            logger.info("Shutting down MCP stdio server...")
            shutdown_event.set()
        else:
            os._exit(130)

    try:
        asyncio.get_running_loop().add_signal_handler(signal.SIGINT, _on_sigint)
    except NotImplementedError:
        pass

    run_task = asyncio.create_task(mcp_app.run_stdio_async())
    await asyncio.wait(
        [run_task, asyncio.create_task(shutdown_event.wait())],
        return_when=asyncio.FIRST_COMPLETED,
    )
    if shutdown_event.is_set() and not run_task.done():
        run_task.cancel()
        await asyncio.sleep(0)
    await app.stop()
    if shutdown_event.is_set():
        os._exit(130)


async def run_stdio() -> None:
    """Start an MCP stdio server and register tools.

    Loads the MCP SDK, initializes adapters (if configured), registers tools,
    and serves over stdio until interrupted.
    """
    mcp_cls, _ = _load_mcp_sdk()
    if mcp_cls is None:
        raise RuntimeError(
            "MCP SDK not installed. Please install the Python MCP SDK (e.g.,\n"
            "    pip install mcp\n"
            "and then re-run: python -m src.server.mcp_stdio"
        )
    mcp_app = cast(Any, mcp_cls)("domain-mcp-server")
    _init_adapters_from_env()
    log_plugin_status()

    # Initialize MCP Resources registry at startup
    try:
        from .resources import get_registry

        registry = get_registry()
        logger.info(f"Loaded {len(registry.resources)} MCP resources")
    except Exception as exc:
        logger.warning(f"Failed to load MCP resources: {exc}")

    app = DomainMCPServer()
    await app.start()
    _register_tools(mcp_app, app)
    await _serve_forever(mcp_app, app)


def main() -> None:
    """CLI entrypoint: run the MCP stdio server.

    Supports optional environment variable ``DOMAIN_MCP_LOG_LEVEL`` and
    respects global setup when invoked under the main CLI runner.
    """
    # Prefer previously configured logging; if none, set up from env
    if not logging.getLogger().hasHandlers():
        setup_logging(os.environ.get("DOMAIN_MCP_LOG_LEVEL", "INFO"))
    try:
        asyncio.run(run_stdio())
    except KeyboardInterrupt:
        # Suppress traceback on Ctrl-C for a clean exit
        pass


if __name__ == "__main__":
    main()
