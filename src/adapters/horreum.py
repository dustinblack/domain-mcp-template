"""Horreum Source MCP adapter.

This adapter translates the Source MCP Contract into HTTP requests to a
Horreum MCP server instance. It encapsulates transport concerns (base URL,
headers, timeouts) and exposes a typed interface for contract operations that
return validated Pydantic models.

Notes
-----
- The current implementation returns placeholder responses for list/get
  methods. In a subsequent milestone these will be wired to real HTTP calls
  against the Horreum MCP endpoints.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from .. import __version__
from ..schemas.source_mcp_contract import (  # Label values (Phase 2.5)
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
from ..utils.correlation import get_request_id

logger = logging.getLogger(__name__)


class HorreumAdapter:
    """Adapter for the Horreum MCP.

    Parameters
    ----------
    endpoint: str
        Base URL of the Horreum MCP HTTP API (e.g., "http://localhost:3001").
    api_key: Optional[str]
        Optional bearer token for authenticating requests.
    timeout: int
        Request timeout in seconds for all HTTP operations.

    Attributes
    ----------
    _client: httpx.AsyncClient
        Shared async client configured with base URL, timeout, and headers.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        timeout: int = 30,
        *,
        max_retries: int = 1,
        backoff_initial_ms: int = 200,
        backoff_multiplier: float = 2.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=endpoint, timeout=timeout, headers=self._headers(api_key)
        )
        self._session_id: Optional[str] = None
        self._max_retries = max(0, int(max_retries))
        self._backoff_initial_ms = max(0, int(backoff_initial_ms))
        self._backoff_multiplier = max(1.0, float(backoff_multiplier))
        self._timeout_seconds = timeout  # Store for error messages
        logger.info(
            "horreum.adapter.init",
            extra={"endpoint": endpoint, "timeout_seconds": timeout},
        )

    def inject_http_client_for_testing(self, client: Any) -> None:
        """Replace underlying HTTP client (testing only).

        This allows unit tests to provide a mock compatible with ``post()``.
        """
        self._client = client

    async def _post_json(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST JSON to an endpoint and return parsed JSON with error handling.

        Parameters
        ----------
        path: str
            Relative URL path for the tool endpoint (e.g., "/tools/tests.list").
        payload: Dict[str, Any]
            JSON-serializable request body.

        Returns
        -------
        Dict[str, Any]
            Parsed JSON object from the response body.

        Raises
        ------
        httpx.HTTPError
            On transport errors or non-2xx responses.
        ValueError
            If response body is not valid JSON.
        """
        logger.debug(
            "horreum.http.post",
            extra={
                "req_id": get_request_id(),
                "path": path,
                "payload_keys": list(payload.keys()),
            },
        )
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt <= self._max_retries:
            try:
                if self._session_id:
                    resp = await self._client.post(
                        path,
                        json=payload,
                        headers={"mcp-session-id": self._session_id},
                    )
                else:
                    # Keep signature compatible with tests' mock client
                    resp = await self._client.post(path, json=payload)
                resp.raise_for_status()
                break
            except httpx.ReadTimeout as exc:
                last_exc = exc
                # Log timeout with helpful context
                logger.warning(
                    "horreum.http.timeout",
                    extra={
                        "path": path,
                        "attempt": attempt + 1,
                        "max_retries": self._max_retries,
                        "timeout_seconds": self._timeout_seconds,
                        "hint": (
                            f"Request to {path} timed out after "
                            f"{self._timeout_seconds}s. Consider increasing "
                            f"timeout_seconds in config (current: "
                            f"{self._timeout_seconds}s, recommended: 300s)"
                        ),
                    },
                )
                delay = (self._backoff_initial_ms / 1000.0) * (
                    self._backoff_multiplier**attempt
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            except httpx.ConnectError as exc:
                last_exc = exc
                delay = (self._backoff_initial_ms / 1000.0) * (
                    self._backoff_multiplier**attempt
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                # Capture truncated upstream body for diagnostics
                body_preview = ""
                try:
                    text = exc.response.text
                    if text:
                        body_preview = text if len(text) <= 500 else text[:500] + "..."
                except Exception:  # pragma: no cover - defensive
                    body_preview = "(unavailable)"
                reinit_hdr = exc.response.headers.get(
                    "mcp-session-reinit"
                ) or exc.response.headers.get("mcp-session-id-expired")
                if (
                    exc.response.status_code in (401, 403, 429, 440, 503) or reinit_hdr
                ) and attempt < self._max_retries:
                    # Try session init on auth/session issues
                    if exc.response.status_code in (401, 403, 440) or reinit_hdr:
                        sid = await self.init_session()
                        if sid:
                            self._session_id = sid
                    await asyncio.sleep(self._backoff_initial_ms / 1000.0)
                    attempt += 1
                    continue
                logger.error(
                    "horreum.http.status_error",
                    extra={
                        "req_id": get_request_id(),
                        "path": path,
                        "status": exc.response.status_code,
                        "body_preview": body_preview,
                    },
                )
                raise
        else:
            if last_exc is not None:
                raise last_exc
            raise RuntimeError(
                "HorreumAdapter request failed after retries without exception"
            )
        data = resp.json()
        logger.debug(
            "horreum.http.response",
            extra={
                "req_id": get_request_id(),
                "path": path,
                "status_code": resp.status_code,
            },
        )
        return data

    async def init_session(self) -> Optional[str]:
        """Initialize an MCP session with the Horreum MCP server.

        Attempts to POST to ``/mcp/initialize`` and capture the returned
        session identifier. If successful, subsequent tool calls will include
        the ``mcp-session-id`` header.

        Returns
        -------
        Optional[str]
            The new session id if created; otherwise ``None``.
        """
        try:
            resp = await self._client.post("/mcp/initialize", json={})
            resp.raise_for_status()
            data = resp.json()
            sid = data.get("session_id") or data.get("sessionId")
            if isinstance(sid, str) and sid:
                self._session_id = sid
                return sid
            # Fallback: some servers might return header
            sid_hdr = resp.headers.get("mcp-session-id")
            if sid_hdr:
                self._session_id = sid_hdr
                return sid_hdr
        except httpx.HTTPError:
            return None
        return None

    @staticmethod
    def _headers(api_key: Optional[str]) -> dict:
        """Build default headers.

        Parameters
        ----------
        api_key: Optional[str]
            Bearer token to attach as an Authorization header.

        Returns
        -------
        dict
            A dictionary of HTTP headers suitable for JSON requests.
        """
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def source_describe(
        self, req: SourceDescribeRequest
    ) -> SourceDescribeResponse:
        """Describe Horreum source capabilities.

        Parameters
        ----------
        req: SourceDescribeRequest
            Empty request structure for source.describe.

        Returns
        -------
        SourceDescribeResponse
            Declares source type, implementation version, and contract support.
        """
        _ = req
        return SourceDescribeResponse(
            source_type=SourceType.HORREUM,
            version=__version__,
            contract_version=ContractVersion.V1_0_0,
            capabilities=SourceCapabilities(),
            limits=SourceLimits(
                max_page_size=1000,
                max_dataset_size=None,
                rate_limit_per_minute=None,
            ),
        )

    async def tests_list(self, req: TestsListRequest) -> TestsListResponse:
        """List tests from Horreum MCP.

        Parameters
        ----------
        req: TestsListRequest
            Request containing filters and pagination.

        Returns
        -------
        TestsListResponse
            A page of tests; currently empty until HTTP wiring is added.
        """
        # Translate Source MCP Contract fields to Horreum MCP fields
        payload: Dict[str, Any] = {}
        if req.query:
            payload["name"] = req.query  # Horreum MCP uses "name" for text search
        if req.page_size:
            payload["limit"] = req.page_size  # Horreum MCP uses "limit"
        if req.page_token:
            payload["page_token"] = req.page_token

        data = await self._post_json("/api/tools/horreum_list_tests", payload)

        # Convert numeric IDs to strings for Pydantic validation
        if "tests" in data:
            for test in data["tests"]:
                if "id" in test and isinstance(test["id"], int):
                    test["id"] = str(test["id"])
                if "test_id" in test and isinstance(test["test_id"], int):
                    test["test_id"] = str(test["test_id"])

        return TestsListResponse.model_validate(data)

    async def runs_list(self, req: RunsListRequest) -> RunsListResponse:
        """List runs for a test from Horreum MCP.

        Parameters
        ----------
        req: RunsListRequest
            Request containing the target test and filters.

        Returns
        -------
        RunsListResponse
            A page of runs; currently empty until HTTP wiring is added.
        """
        payload = req.model_dump(by_alias=True, exclude_none=True)

        # Convert test_id to integer for Horreum MCP API
        if "test_id" in payload:
            try:
                payload["test_id"] = int(payload["test_id"])
            except (ValueError, TypeError):
                pass  # Keep as-is if conversion fails

        data = await self._post_json("/api/tools/horreum_list_runs", payload)

        # Convert numeric IDs to strings for Pydantic validation
        if "runs" in data:
            for run in data["runs"]:
                if "run_id" in run and isinstance(run["run_id"], int):
                    run["run_id"] = str(run["run_id"])
                if "test_id" in run and isinstance(run["test_id"], int):
                    run["test_id"] = str(run["test_id"])

        return RunsListResponse.model_validate(data)

    async def datasets_search(
        self, req: DatasetsSearchRequest
    ) -> DatasetsSearchResponse:
        """Search datasets in Horreum MCP.

        Parameters
        ----------
        req: DatasetsSearchRequest
            Request containing search filters and pagination.

        Returns
        -------
        DatasetsSearchResponse
            A page of datasets; currently empty until HTTP wiring is added.
        """
        payload = req.model_dump(by_alias=True, exclude_none=True)

        # Convert test_id to integer for Horreum MCP API
        if "test_id" in payload:
            try:
                payload["test_id"] = int(payload["test_id"])
            except (ValueError, TypeError):
                pass  # Keep as-is if conversion fails

        # Convert run_ids list to integers for Horreum MCP API
        if "run_ids" in payload and isinstance(payload["run_ids"], list):
            try:
                payload["run_ids"] = [int(rid) for rid in payload["run_ids"]]
            except (ValueError, TypeError):
                pass  # Keep as-is if conversion fails

        # Debug logging to see what we're sending to Horreum MCP
        import json

        logger.info(f"horreum_list_datasets PAYLOAD: {json.dumps(payload)}")

        data = await self._post_json("/api/tools/horreum_list_datasets", payload)

        # Convert numeric IDs to strings for Pydantic validation
        if "datasets" in data:
            for dataset in data["datasets"]:
                if "dataset_id" in dataset and isinstance(dataset["dataset_id"], int):
                    dataset["dataset_id"] = str(dataset["dataset_id"])
                if "run_id" in dataset and isinstance(dataset["run_id"], int):
                    dataset["run_id"] = str(dataset["run_id"])
                if "test_id" in dataset and isinstance(dataset["test_id"], int):
                    dataset["test_id"] = str(dataset["test_id"])

        return DatasetsSearchResponse.model_validate(data)

    async def datasets_get(self, req: DatasetsGetRequest) -> DatasetsGetResponse:
        """Fetch a dataset body by id.

        Parameters
        ----------
        req: DatasetsGetRequest
            Request containing the dataset identifier.

        Returns
        -------
        DatasetsGetResponse
            A response with content; currently empty until HTTP wiring is added.
        """
        payload = req.model_dump(by_alias=True, exclude_none=True)

        # Convert dataset_id to integer for Horreum MCP API
        if "dataset_id" in payload:
            try:
                payload["dataset_id"] = int(payload["dataset_id"])
            except (ValueError, TypeError):
                pass  # Keep as-is if conversion fails

        data = await self._post_json("/api/tools/horreum_get_dataset", payload)

        # Convert numeric IDs to strings for Pydantic validation
        if "dataset_id" in data and isinstance(data["dataset_id"], int):
            data["dataset_id"] = str(data["dataset_id"])
        if "run_id" in data and isinstance(data["run_id"], int):
            data["run_id"] = str(data["run_id"])
        if "test_id" in data and isinstance(data["test_id"], int):
            data["test_id"] = str(data["test_id"])

        return DatasetsGetResponse.model_validate(data)

    async def artifacts_get(self, req: ArtifactsGetRequest) -> ArtifactsGetResponse:
        """Fetch an artifact for a run.

        Parameters
        ----------
        req: ArtifactsGetRequest
            Request specifying the run identifier and artifact name/path.

        Returns
        -------
        ArtifactsGetResponse
            Artifact content; currently empty until HTTP wiring is added.
        """
        payload = req.model_dump(by_alias=True, exclude_none=True)

        # Convert run_id to integer for Horreum MCP API
        if "run_id" in payload:
            try:
                payload["run_id"] = int(payload["run_id"])
            except (ValueError, TypeError):
                pass  # Keep as-is if conversion fails

        data = await self._post_json("/api/tools/horreum_get_artifact", payload)
        return ArtifactsGetResponse.model_validate(data)

    # ---------------- Label values (Phase 2.5) ----------------

    async def get_run_label_values(
        self, req: RunLabelValuesRequest
    ) -> RunLabelValuesResponse:
        """Fetch label values for a run via Horreum MCP.

        Maps Domain request fields to Horreum MCP endpoint:
        POST /api/tools/horreum_get_run_label_values
        """
        payload = req.model_dump(by_alias=True, exclude_none=True)
        # Convert run_id to integer if possible for Horreum API
        try:
            payload["run_id"] = int(payload["run_id"])  # type: ignore[assignment]
        except (ValueError, TypeError):
            pass
        data = await self._post_json("/api/tools/horreum_get_run_label_values", payload)
        # Normalize ids to strings if present
        if "items" in data:
            for item in data["items"]:
                if "run_id" in item and isinstance(item["run_id"], int):
                    item["run_id"] = str(item["run_id"])
                if "dataset_id" in item and isinstance(item["dataset_id"], int):
                    item["dataset_id"] = str(item["dataset_id"])
                # Also coerce nested label value ids
                for lv in item.get("values", []) or []:
                    if isinstance(lv, dict) and isinstance(lv.get("id"), int):
                        lv["id"] = str(lv["id"])
        return RunLabelValuesResponse.model_validate(data)

    async def get_test_label_values(
        self, req: TestLabelValuesRequest
    ) -> TestLabelValuesResponse:
        """Fetch aggregated label values for a test via Horreum MCP.

        POST /api/tools/horreum_get_test_label_values
        """
        payload = req.model_dump(by_alias=True, exclude_none=True)
        # Convert test_id to integer when possible
        try:
            payload["test_id"] = int(payload["test_id"])  # type: ignore[assignment]
        except (ValueError, TypeError):
            pass
        data = await self._post_json(
            "/api/tools/horreum_get_test_label_values", payload
        )
        if "items" in data:
            for item in data["items"]:
                if "run_id" in item and isinstance(item["run_id"], int):
                    item["run_id"] = str(item["run_id"])
                if "dataset_id" in item and isinstance(item["dataset_id"], int):
                    item["dataset_id"] = str(item["dataset_id"])
                for lv in item.get("values", []) or []:
                    if isinstance(lv, dict) and isinstance(lv.get("id"), int):
                        lv["id"] = str(lv["id"])
        return TestLabelValuesResponse.model_validate(data)

    async def get_dataset_label_values(
        self, req: DatasetLabelValuesRequest
    ) -> DatasetLabelValuesResponse:
        """Fetch label values for a dataset via Horreum MCP.

        POST /api/tools/horreum_get_dataset_label_values
        """
        payload = req.model_dump(by_alias=True, exclude_none=True)
        # Convert dataset_id to integer when possible
        try:
            payload["dataset_id"] = int(
                payload["dataset_id"]
            )  # type: ignore[assignment]
        except (ValueError, TypeError):
            pass
        data = await self._post_json(
            "/api/tools/horreum_get_dataset_label_values", payload
        )
        # Coerce LabelValue.id to string where numeric
        if "values" in data:
            for lv in data.get("values", []) or []:
                if isinstance(lv, dict) and isinstance(lv.get("id"), int):
                    lv["id"] = str(lv["id"])
        return DatasetLabelValuesResponse.model_validate(data)
