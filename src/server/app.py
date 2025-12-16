"""Minimal Domain MCP server skeleton.

This module provides a future-facing structure for the Domain MCP server. It
does not yet implement the full MCP protocol or network bindings. Instead, it
offers an asynchronous lifecycle that can host tool registrations and shared
infrastructure (e.g., adapters, caches, observability) in subsequent
milestones.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from ..adapters import get_adapter, get_available_source_ids
from ..domain.plugins import get as get_plugin
from ..schemas.source_mcp_contract import (
    RunLabelValuesRequest,
    TestLabelValuesRequest,
)

logger = logging.getLogger(__name__)


class DomainMCPServer:
    """Placeholder async server app.

    Responsibilities (future):
    - Integrate with an MCP server framework
    - Register tool handlers that implement the Domain MCP tool surface
    - Manage shared resources (adapters, caches, tracing)
    - Provide graceful startup/shutdown hooks
    """

    def __init__(self) -> None:
        """Create a new server instance with stopped state."""
        self._started: bool = False

    async def start(self) -> None:
        """Start the server runtime.

        Behavior
        --------
        - Marks the server as started and prepares for future tool registration.
        - Idempotent: repeated calls are safe and have no effect after start.
        """
        if self._started:
            logger.debug("server.start no-op: already started")
            return
        self._started = True
        logger.info("server.started")

    async def stop(self) -> None:
        """Stop the server runtime.

        Ensures cleanup hooks are called in future implementations. Idempotent.
        """
        if not self._started:
            logger.debug("server.stop no-op: not started")
            return
        self._started = False
        logger.info("server.stopped")

    async def get_key_metrics_raw(
        self,
        dataset_types: List[str],
        data: List[object],
        os_filter: str | None = None,
        run_type_filter: str | None = None,
    ):
        """Extract metric points from raw dataset JSON using plugins.

        This is a minimal Phase 2 handler for raw mode only.

        Parameters
        ----------
        dataset_types : List[str]
            Plugin identifiers to use for extraction
        data : List[object]
            Raw dataset JSON bodies
        os_filter : str | None
            Optional OS ID filter (e.g., "rhel", "autosd")
        run_type_filter : str | None
            Optional run type filter (e.g., "nightly", "ci", "release")
        """
        logger.debug(
            "metrics.extract start",
            extra={
                "dataset_types": dataset_types,
                "datasets": len(data),
                "os_filter": os_filter,
                "run_type_filter": run_type_filter,
            },
        )
        points: List[object] = []
        for plugin_id in dataset_types:
            plugin = get_plugin(plugin_id)
            for body in data:
                extracted = await plugin.extract(
                    body,
                    refs={},
                    os_filter=os_filter,
                    run_type_filter=run_type_filter,
                )
                points.extend(extracted)
        logger.debug("metrics.extract done", extra={"points": len(points)})
        return points

    async def prefer_label_values_when_available(
        self,
        dataset_types: List[str],
        *,
        test_id: str | None = None,
        run_id: str | None = None,
        source_id: str | None = None,
        before: str | None = None,
        after: str | None = None,
        page_size: int = 100,
        os_filter: str | None = None,
        run_type_filter: str | None = None,
    ) -> List[object]:
        """Fetch label values when adapter and inputs allow; else return [].

        Only supports boot-time-verbose for now. Does not perform fallback; the
        caller should fall back to dataset parsing if this returns empty.

        Parameters
        ----------
        os_filter : str | None
            If provided, filters results by OS ID label (e.g., "rhel", "autosd")
            Uses Horreum's multiFilter for server-side filtering.
        run_type_filter : str | None
            If provided, filters by Run type (e.g., "nightly", "ci", "release")
            Modern data: Filters by 'Run type' label
            Legacy data: Falls back to 'Test Description' label search
            Uses Horreum's multiFilter for server-side filtering.
        """
        if "boot-time-verbose" not in dataset_types:
            return []
        # Require at least a source and either run_id or test_id context
        if not source_id:
            srcs = get_available_source_ids()
            if srcs:
                source_id = srcs[0]
            else:
                return []
        try:
            adapter = get_adapter(source_id)
        except KeyError:
            return []

        # Prefer run-specific when provided, else test aggregation with time bounds
        try:
            if run_id:
                resp = await adapter.get_run_label_values(
                    RunLabelValuesRequest.model_validate(
                        {
                            "run_id": run_id,
                            "page_size": page_size,
                        }
                    )
                )
                return [i.model_dump() for i in resp.items]
            if test_id:
                payload: Dict[str, Any] = {
                    "test_id": test_id,
                    "page_size": page_size,
                    # Request BOTH metrics and filtering (dimension) labels
                    # Default is metrics=True, filtering=False which excludes
                    # dimension labels like OS ID, Mode, Target
                    "metrics": True,
                    "filtering": True,
                }
                if before:
                    payload["before"] = before
                if after:
                    payload["after"] = after
                # Add filters via filter parameter with multiFilter flag
                filter_dict: Dict[str, List[str]] = {}
                if os_filter:
                    filter_dict["OS ID"] = [os_filter]
                if run_type_filter:
                    # Modern data: Filter by 'Run type' label
                    # Note: multiFilter only supports exact matches, so we
                    # can't filter legacy data (where "nightly" appears in
                    # "Test Description") at the Horreum API level. We'll
                    # need client-side filtering for that.
                    filter_dict["Run type"] = [run_type_filter]
                if filter_dict:
                    payload["filter"] = filter_dict
                    payload["multiFilter"] = True
                resp2 = await adapter.get_test_label_values(
                    TestLabelValuesRequest.model_validate(payload)
                )
                return [i.model_dump() for i in resp2.items]
        except (KeyError, ValueError, TypeError):
            # Non-fatal: swallow and return [] to allow fallback path
            return []
        except Exception:
            # Catch httpx.HTTPStatusError (404 when endpoint not available) and
            # any other adapter exceptions to allow fallback to datasets path
            return []
        return []

    def build_horreum_fetch_plan(
        self,
        *,
        test_id: str | None,
        schema_uri: str | None,
        limit: int,
    ) -> List[Dict[str, object]]:
        """Build a client-executable fetch plan (datasets.search + get).

        Returns a list of tool invocations with args matching the Source MCP
        contract (suitable for execution by an AI client already connected to
        the Horreum MCP).
        """
        plan: List[Dict[str, object]] = []
        plan.append(
            {
                "tool": "datasets.search",
                "args": {
                    "test_id": test_id,
                    "schema_uri": schema_uri,
                    "page_size": limit,
                },
            }
        )
        # Client should iterate results and call datasets.get for each id; we
        # emit a template step indicating that behavior.
        plan.append(
            {
                "tool": "datasets.get",
                "args": {"dataset_id": "<id from datasets.search>"},
            }
        )
        return plan

    async def compute_statistics_stub(self) -> dict:
        """Placeholder compute_statistics returning an empty result set."""
        return {"results": []}

    async def generate_report_stub(
        self, template_id: str, fmt: str = "markdown"
    ) -> str:
        """Placeholder generate_report returning minimal content."""
        _ = fmt
        return f"# Report: {template_id}\n\n_No content yet_\n"


async def main() -> None:
    """Run the server until interrupted (development use)."""
    server = DomainMCPServer()
    await server.start()

    # Placeholder: keep running until cancelled
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
