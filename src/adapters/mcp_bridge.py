"""MCP stdio bridge adapter.

This adapter speaks the Source MCP Contract by invoking another MCP server's
tools over stdio using an MCP client. It enables Domain MCP to reach a
Horreum MCP that is only available via stdio (no HTTP).

Runtime note: A Python MCP client must be available. We defer-import the
client and raise a clear error if not installed. Tests inject a mock client.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, Optional

from .. import __version__
from ..schemas.source_mcp_contract import (
    ArtifactsGetRequest,
    ArtifactsGetResponse,
    ContractVersion,
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
    SourceCapabilities,
    SourceDescribeRequest,
    SourceDescribeResponse,
    SourceLimits,
    SourceType,
    TestLabelValuesRequest,
    TestLabelValuesResponse,
    TestsListRequest,
    TestsListResponse,
)

logger = logging.getLogger(__name__)


class MCPBridgeAdapter:
    """Adapter that calls a Source MCP over stdio using an MCP client.

    Parameters
    ----------
    command: Optional[str]
        Executable path to spawn the stdio MCP server (e.g., "python").
        If not provided, the adapter expects an injected client.
    args: Optional[list[str]]
        Command-line args for the spawned process (e.g., ["-m", "horreum_mcp"]).
    timeout: int
        Request timeout in seconds for tool invocations.
    """

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[list[str]] = None,
        timeout: int = 30,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self._command = command
        self._args = args or []
        self._timeout = timeout
        self._env = env or {}
        self._client: Optional[Any] = None
        self._client_context: Optional[Any] = None

    def inject_client_for_testing(self, client: Any) -> None:
        """Inject a pre-built MCP client (tests).

        The client must expose ``async def call_tool(name: str, args: dict)``.
        """
        self._client = client

    async def _ensure_client(self) -> Any:
        """Ensure an MCP client session is available.

        Creates a stdio session if one has not been injected.
        """
        if self._client is not None:
            return self._client
        # Lazy import and create stdio client if possible
        try:
            stdio_mod = importlib.import_module("mcp.client.stdio")
        except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
            raise RuntimeError(
                "MCP client not installed; install Python MCP SDK"
            ) from exc

        if not self._command:
            raise RuntimeError(
                "Stdio bridge requires 'command' to spawn the source MCP process"
            )

        # Build stdio client context manager
        create_stdio = getattr(stdio_mod, "stdio_client", None)
        server_params_cls = getattr(stdio_mod, "StdioServerParameters", None)
        if create_stdio is None or server_params_cls is None:  # pragma: no cover
            raise RuntimeError("MCP client API not available in installed SDK")

        # Create server parameters
        server_params = server_params_cls(
            command=self._command, args=self._args, env=self._env
        )

        # Store the context manager for use in _call method
        self._client_context = create_stdio(server_params)
        self._client = "context_manager_ready"
        return self._client

    # Helper to invoke a tool and return parsed JSON
    async def _call(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a remote tool via MCP client and return JSON body."""
        logger.debug(
            "mcp_bridge.call start",
            extra={"tool": tool_name, "payload_keys": list(payload.keys())},
        )

        # Check if we have an injected mock client for testing
        if self._client is not None and self._client != "context_manager_ready":
            call = getattr(self._client, "call_tool", None)
            if call is None:  # pragma: no cover
                raise RuntimeError("Injected MCP client lacks 'call_tool' method")
            return await call(tool_name, payload)

        # Use real stdio client path
        await self._ensure_client()  # Ensure context manager is ready

        # Use the MCP client context manager with timeout
        if self._client_context is None:
            raise RuntimeError("Client context not initialized")

        import asyncio

        async def _call_with_session():
            async with self._client_context as (read_stream, write_stream):
                from mcp.client.session import ClientSession

                session = ClientSession(read_stream, write_stream)
                await session.initialize()

                # Call the remote tool
                result = await session.call_tool(tool_name, payload)
                # Convert content to dict - assuming it's JSON-serializable
                if hasattr(result.content, "__dict__"):
                    return result.content.__dict__
                elif isinstance(result.content, list) and result.content:
                    # Handle list of content items by taking the first text content
                    first_item = result.content[0]
                    if hasattr(first_item, "text"):
                        import json

                        return json.loads(first_item.text)
                return {"content": str(result.content)}

        # Apply timeout to the entire operation
        try:
            logger.debug(
                "mcp_bridge.session starting",
                extra={"tool": tool_name, "timeout_seconds": self._timeout},
            )
            result = await asyncio.wait_for(_call_with_session(), timeout=self._timeout)
            logger.debug("mcp_bridge.session success", extra={"tool": tool_name})
            return result
        except asyncio.TimeoutError:
            logger.warning(
                "mcp_bridge.session timeout",
                extra={"tool": tool_name, "timeout_seconds": self._timeout},
            )
            raise RuntimeError(
                f"MCP bridge call timed out after {self._timeout}s for tool "
                f"'{tool_name}'"
            )

    async def source_describe(
        self, req: SourceDescribeRequest
    ) -> SourceDescribeResponse:
        """Return static bridge capabilities without remote call."""
        # Local capabilities for the bridge; does not call remote.
        _ = req
        return SourceDescribeResponse(
            source_type=SourceType.HORREUM,
            version=__version__,
            contract_version=ContractVersion.V1_0_0,
            capabilities=SourceCapabilities(),
            limits=SourceLimits(
                max_page_size=1000, max_dataset_size=None, rate_limit_per_minute=None
            ),
        )

    async def tests_list(self, req: TestsListRequest) -> TestsListResponse:
        """Proxy tests.list to the remote Source MCP over stdio."""
        data = await self._call(
            "tests.list", req.model_dump(by_alias=True, exclude_none=True)
        )
        return TestsListResponse.model_validate(data)

    async def runs_list(self, req: RunsListRequest) -> RunsListResponse:
        """Proxy runs.list to the remote Source MCP over stdio."""
        data = await self._call(
            "runs.list", req.model_dump(by_alias=True, exclude_none=True)
        )
        return RunsListResponse.model_validate(data)

    async def datasets_search(
        self, req: DatasetsSearchRequest
    ) -> DatasetsSearchResponse:
        """Proxy datasets.search to the remote Source MCP over stdio."""
        data = await self._call(
            "datasets.search", req.model_dump(by_alias=True, exclude_none=True)
        )
        return DatasetsSearchResponse.model_validate(data)

    async def datasets_get(self, req: DatasetsGetRequest) -> DatasetsGetResponse:
        """Proxy datasets.get to the remote Source MCP over stdio."""
        data = await self._call(
            "datasets.get", req.model_dump(by_alias=True, exclude_none=True)
        )
        return DatasetsGetResponse.model_validate(data)

    async def artifacts_get(self, req: ArtifactsGetRequest) -> ArtifactsGetResponse:
        """Proxy artifacts.get to the remote Source MCP over stdio."""
        data = await self._call(
            "artifacts.get", req.model_dump(by_alias=True, exclude_none=True)
        )
        return ArtifactsGetResponse.model_validate(data)

    async def get_run_label_values(
        self, req: RunLabelValuesRequest
    ) -> RunLabelValuesResponse:
        """Proxy run_label_values.get to the remote Source MCP over stdio."""
        data = await self._call(
            "run_label_values.get", req.model_dump(by_alias=True, exclude_none=True)
        )
        return RunLabelValuesResponse.model_validate(data)

    async def get_test_label_values(
        self, req: TestLabelValuesRequest
    ) -> TestLabelValuesResponse:
        """Proxy test_label_values.get to the remote Source MCP over stdio."""
        data = await self._call(
            "test_label_values.get", req.model_dump(by_alias=True, exclude_none=True)
        )
        return TestLabelValuesResponse.model_validate(data)

    async def get_dataset_label_values(
        self, req: DatasetLabelValuesRequest
    ) -> DatasetLabelValuesResponse:
        """Proxy dataset_label_values.get to the remote Source MCP over stdio."""
        data = await self._call(
            "dataset_label_values.get", req.model_dump(by_alias=True, exclude_none=True)
        )
        return DatasetLabelValuesResponse.model_validate(data)
