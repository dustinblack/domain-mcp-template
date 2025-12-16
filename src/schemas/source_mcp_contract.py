"""
Source MCP Contract Schemas

Code-first schema definitions using Pydantic that serve as:
1. Runtime validation for requests/responses
2. OpenAPI/JSON Schema generation for documentation
3. Type hints for development
4. Test fixtures and validation

This replaces documentation-only schemas with executable code.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class ContractVersion(str, Enum):
    """Source MCP Contract version"""

    V1_0_0 = "1.0.0"


class SourceType(str, Enum):
    """Known source types"""

    HORREUM = "horreum"
    CUSTOM = "custom-backend"
    DATA_WAREHOUSE = "data-warehouse"
    ELASTICSEARCH = "elasticsearch"


class ErrorCode(str, Enum):
    """Standardized error codes"""

    INVALID_REQUEST = "INVALID_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


class MergeStrategy(str, Enum):
    """Data source merging strategies for get_key_metrics queries

    Controls how the server retrieves and combines data from multiple sources
    (label values, datasets, runs).
    """

    PREFER_FAST = "prefer_fast"
    """Try label values first (fast, pre-aggregated), fallback to datasets if empty.
    This is the default behavior - prioritizes speed and efficiency."""

    COMPREHENSIVE = "comprehensive"
    """Fetch from both label values AND datasets, merge results.
    Use when you need both aggregated metrics (from labels) and detailed data
    (from datasets) in a single query."""

    LABELS_ONLY = "labels_only"
    """Only use label values, fail if unavailable.
    Use when you specifically need pre-aggregated server-side data and don't
    want fallback."""

    DATASETS_ONLY = "datasets_only"
    """Skip label values, go straight to datasets.
    Use when you need raw data or when labels are known to be incomplete."""


# Common Models


class CacheInfo(BaseModel):
    """Cache metadata for conditional requests"""

    etag: Optional[str] = None
    last_modified: Optional[datetime] = None
    max_age: Optional[int] = Field(None, ge=0, description="Cache TTL in seconds")


class Pagination(BaseModel):
    """Pagination metadata"""

    next_page_token: Optional[str] = None
    has_more: bool
    total_count: Optional[int] = Field(None, ge=0)


class ErrorDetails(BaseModel):
    """Structured error response"""

    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = Field(
        None, ge=0, description="Seconds to wait before retry"
    )
    retryable: Optional[bool] = None


class ErrorResponse(BaseModel):
    """Standard error response wrapper"""

    error: ErrorDetails


# source.describe


class SourceCapabilities(BaseModel):
    """Source MCP implementation capabilities"""

    pagination: bool = True
    caching: bool = True
    streaming: bool = False
    schemas: bool = False


class SourceLimits(BaseModel):
    """Source MCP operational limits"""

    max_page_size: Optional[int] = Field(None, ge=1)
    max_dataset_size: Optional[int] = Field(None, ge=1)
    rate_limit_per_minute: Optional[int] = Field(None, ge=1)


class SourceDescribeRequest(BaseModel):
    """Empty request for source.describe"""


class SourceDescribeResponse(BaseModel):
    """Response from source.describe"""

    source_type: SourceType = Field(..., description="Backend type identifier")
    version: str = Field(
        ..., pattern=r"^\d+\.\d+\.\d+$", description="Source MCP implementation version"
    )
    contract_version: ContractVersion = Field(
        ..., description="Source MCP Contract version supported"
    )
    capabilities: SourceCapabilities
    limits: Optional[SourceLimits] = None


# tests.list


class TestsListRequest(BaseModel):
    """Request for tests.list"""

    query: Optional[str] = Field(
        None, description="Text search query for test names/descriptions"
    )
    tags: Optional[List[str]] = Field(None, description="Filter by test tags")
    page_token: Optional[str] = Field(None, description="Opaque pagination token")
    page_size: int = Field(100, ge=1, le=1000, description="Number of items per page")


class TestInfo(BaseModel):
    """Test metadata"""

    test_id: str
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestsListResponse(BaseModel):
    """Response from tests.list"""

    tests: List[TestInfo]
    pagination: Pagination
    cache_info: Optional[CacheInfo] = None


# runs.list


class RunStatus(str, Enum):
    """Test run status"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunsListRequest(BaseModel):
    """Request for runs.list"""

    test_id: str = Field(..., description="Test identifier to list runs for")
    from_time: Optional[str] = Field(
        None,
        alias="from",
        description=(
            "Start of time range filter. Accepts ISO datetime, epoch millis, "
            "or natural language (e.g., 'last week'). "
            "Interpretation is source-dependent."
        ),
    )
    to_time: Optional[str] = Field(
        None,
        alias="to",
        description=(
            "End of time range filter. Accepts ISO datetime, epoch millis, "
            "or natural language (e.g., 'now'). "
            "Interpretation is source-dependent."
        ),
    )
    page_token: Optional[str] = Field(None, description="Opaque pagination token")
    page_size: int = Field(100, ge=1, le=1000, description="Number of items per page")


class RunInfo(BaseModel):
    """Test run metadata"""

    run_id: str
    test_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: RunStatus
    labels: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class RunsListResponse(BaseModel):
    """Response from runs.list"""

    runs: List[RunInfo]
    pagination: Pagination
    cache_info: Optional[CacheInfo] = None


# datasets.search


class DatasetsSearchRequest(BaseModel):
    """Request for datasets.search"""

    test_id: Optional[str] = Field(None, description="Filter by specific test")
    schema_uri: Optional[str] = Field(None, description="Filter by dataset schema URI")
    tags: Optional[List[str]] = Field(None, description="Filter by dataset tags")
    run_ids: Optional[List[str]] = Field(None, description="Filter by specific run IDs")
    from_time: Optional[str] = Field(
        None,
        alias="from",
        description=(
            "Start of time range filter. Accepts ISO datetime, epoch millis, "
            "or natural language (e.g., 'last week'). "
            "Interpretation is source-dependent."
        ),
    )
    to_time: Optional[str] = Field(
        None,
        alias="to",
        description=(
            "End of time range filter. Accepts ISO datetime, epoch millis, "
            "or natural language (e.g., 'now'). "
            "Interpretation is source-dependent."
        ),
    )
    page_token: Optional[str] = Field(None, description="Opaque pagination token")
    page_size: int = Field(100, ge=1, le=1000, description="Number of items per page")


class DatasetInfo(BaseModel):
    """Dataset metadata"""

    dataset_id: str
    run_id: str
    test_id: str
    schema_uri: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    size_bytes: Optional[int] = Field(None, ge=0)
    content_type: str = Field(default="application/json")


class DatasetsSearchResponse(BaseModel):
    """Response from datasets.search"""

    datasets: List[DatasetInfo]
    pagination: Pagination
    cache_info: Optional[CacheInfo] = None


# datasets.get


class DatasetsGetRequest(BaseModel):
    """Request for datasets.get"""

    dataset_id: str = Field(..., description="Dataset identifier to retrieve")
    if_none_match: Optional[str] = Field(
        None, description="ETag for conditional request"
    )
    if_modified_since: Optional[datetime] = Field(
        None, description="Timestamp for conditional request"
    )


class DatasetMetadata(BaseModel):
    """Dataset content metadata"""

    schema_uri: Optional[str] = None
    encoding: Optional[str] = None
    compression: Optional[str] = None


class DatasetsGetResponse(BaseModel):
    """Response from datasets.get"""

    dataset_id: str
    content: Union[Dict[str, Any], str, List[Any]] = Field(
        ..., description="Raw dataset content"
    )
    content_type: str = Field(default="application/json")
    size_bytes: Optional[int] = Field(None, ge=0)
    cache_info: Optional[CacheInfo] = None
    metadata: Optional[DatasetMetadata] = None


# artifacts.get


class ArtifactsGetRequest(BaseModel):
    """Request for artifacts.get"""

    run_id: str = Field(..., description="Run identifier")
    name: str = Field(..., description="Artifact name/path")
    if_none_match: Optional[str] = Field(
        None, description="ETag for conditional request"
    )
    if_modified_since: Optional[datetime] = Field(
        None, description="Timestamp for conditional request"
    )


class ArtifactsGetResponse(BaseModel):
    """Response from artifacts.get"""

    run_id: str
    name: str
    content: str = Field(..., description="Base64 encoded binary content")
    content_type: str = Field(..., description="MIME type of the artifact")
    size_bytes: int = Field(..., ge=0)
    cache_info: Optional[CacheInfo] = None


# ------------------------ Label Values (Phase 2.5) ------------------------


class LabelValue(BaseModel):
    """Single label value record produced by the source system.

    Fields
    -----
    id: str | None
        Optional label identifier (backend-specific).
    name: str
        Canonical label name (e.g., "boot.time.total_ms").
    schema: Optional[str]
        Optional schema URI associated with the label value.
    value: Any
        Raw value (numeric, string, object). Consumers should coerce as needed.
    """

    id: Optional[str] = None
    name: str
    schema_uri: Optional[str] = Field(None, alias="schema")
    value: Any


class ExportedLabelValues(BaseModel):
    """A bundle of label values, typically tied to a run/dataset.

    Fields
    -----
    values: list[LabelValue]
        The exported label values.
    run_id: Optional[str]
        Run identifier if provided by the source system.
    dataset_id: Optional[str]
        Dataset identifier if provided by the source system.
    start: Optional[datetime]
        Optional start timestamp of the observation window.
    stop: Optional[datetime]
        Optional stop timestamp of the observation window.
    """

    values: List[LabelValue] = Field(default_factory=list)
    run_id: Optional[str] = None
    dataset_id: Optional[str] = None
    start: Optional[datetime] = None
    stop: Optional[datetime] = None


class RunLabelValuesRequest(BaseModel):
    """Request for run_label_values.get (Phase 2.5)."""

    # Enable accepting both snake_case (Python) and camelCase (JavaScript)
    # parameter names. Allows clients to use either convention.
    model_config = ConfigDict(populate_by_name=True)

    run_id: str = Field(..., description="Target run identifier")
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    filter: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional JSON sub-document filter expression",
    )
    # Horreum MCP accepts both "multi_filter" and "multiFilter" (2025-10-15)
    # Alias sends canonical camelCase form for JS convention consistency
    multi_filter: bool = Field(
        default=False,
        alias="multiFilter",
        description="Enable array multi-value filtering",
    )
    sort: Optional[str] = Field(
        default=None, description="Optional sort key provided to the source"
    )
    direction: Optional[str] = Field(
        default=None, description="Sort direction: 'asc' or 'desc'"
    )
    page_token: Optional[str] = Field(None, description="Opaque pagination token")
    page_size: int = Field(100, ge=1, le=1000, description="Items per page")


class RunLabelValuesResponse(BaseModel):
    """Response from run_label_values.get (Phase 2.5)."""

    items: List[ExportedLabelValues]
    pagination: Pagination
    cache_info: Optional[CacheInfo] = None


class TestLabelValuesRequest(BaseModel):
    """Request for test_label_values.get (Phase 2.5)."""

    # Enable accepting both snake_case (Python) and camelCase (JavaScript)
    # parameter names. Allows clients to use either convention.
    model_config = ConfigDict(populate_by_name=True)

    test_id: str = Field(..., description="Target test identifier")
    include: List[str] = Field(default_factory=list)
    exclude: List[str] = Field(default_factory=list)
    filter: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional JSON filter expression"
    )
    # Horreum MCP accepts both "multi_filter" and "multiFilter" (2025-10-15)
    # Alias sends canonical camelCase form for JS convention consistency
    multi_filter: bool = Field(
        default=False,
        alias="multiFilter",
        description="Enable array multi-value filtering",
    )
    filtering: bool = Field(
        default=False, description="Request filtering labels only (backend)"
    )
    metrics: bool = Field(default=True, description="Request metrics labels (backend)")
    before: Optional[str] = Field(
        default=None,
        description=(
            "Upper time bound; ISO/epoch/natural language supported by source"
        ),
    )
    after: Optional[str] = Field(
        default=None,
        description=(
            "Lower time bound; ISO/epoch/natural language supported by source"
        ),
    )
    page_token: Optional[str] = Field(None, description="Opaque pagination token")
    page_size: int = Field(100, ge=1, le=1000, description="Items per page")


class TestLabelValuesResponse(BaseModel):
    """Response from test_label_values.get (Phase 2.5)."""

    items: List[ExportedLabelValues]
    pagination: Pagination
    cache_info: Optional[CacheInfo] = None


class DatasetLabelValuesRequest(BaseModel):
    """Request for dataset_label_values.get (Phase 2.5)."""

    dataset_id: str = Field(..., description="Dataset identifier")


class DatasetLabelValuesResponse(BaseModel):
    """Response from dataset_label_values.get (Phase 2.5)."""

    values: List[LabelValue]
    cache_info: Optional[CacheInfo] = None


# schemas.get (optional)


class SchemasGetRequest(BaseModel):
    """Request for schemas.get"""

    schema_uri: str = Field(..., description="Schema URI to retrieve")


class SchemasGetResponse(BaseModel):
    """Response from schemas.get"""

    schema_uri: str
    schema_def: Dict[str, Any] = Field(
        ..., alias="schema", description="JSON Schema definition"
    )
    version: Optional[str] = None
    description: Optional[str] = None


# Contract validation helpers


def validate_contract_compatibility(source_response: SourceDescribeResponse) -> bool:
    """Validate that a source implements minimum contract requirements"""
    return (
        source_response.contract_version == ContractVersion.V1_0_0
        and source_response.capabilities.pagination
        and source_response.capabilities.caching
    )


# Export all schema models for use by the Domain MCP
__all__ = [
    # Core types
    "ContractVersion",
    "SourceType",
    "ErrorCode",
    "CacheInfo",
    "Pagination",
    "ErrorDetails",
    "ErrorResponse",
    # source.describe
    "SourceDescribeRequest",
    "SourceDescribeResponse",
    "SourceCapabilities",
    "SourceLimits",
    # tests.list
    "TestsListRequest",
    "TestsListResponse",
    "TestInfo",
    # runs.list
    "RunsListRequest",
    "RunsListResponse",
    "RunInfo",
    "RunStatus",
    # datasets.search
    "DatasetsSearchRequest",
    "DatasetsSearchResponse",
    "DatasetInfo",
    # datasets.get
    "DatasetsGetRequest",
    "DatasetsGetResponse",
    "DatasetMetadata",
    # artifacts.get
    "ArtifactsGetRequest",
    "ArtifactsGetResponse",
    # Label values (Phase 2.5)
    "LabelValue",
    "ExportedLabelValues",
    "RunLabelValuesRequest",
    "RunLabelValuesResponse",
    "TestLabelValuesRequest",
    "TestLabelValuesResponse",
    "DatasetLabelValuesRequest",
    "DatasetLabelValuesResponse",
    # schemas.get
    "SchemasGetRequest",
    "SchemasGetResponse",
    # Validation
    "validate_contract_compatibility",
]
