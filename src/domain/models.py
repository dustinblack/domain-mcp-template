"""Canonical domain data model used by plugins and tools.

These Pydantic models represent source-agnostic references and observations
that domain plugins produce and tool handlers consume. Keeping the model small
and stable allows plugins to target a consistent shape regardless of the source
backend or dataset schema version.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DomainRunRef(BaseModel):
    """Reference to a test run in the source system.

    Attributes
    ----------
    run_id: str
        Unique identifier of the run in the source system.
    test_id: str
        Identifier of the test to which the run belongs.
    started_at: datetime
        Timestamp when the run started (UTC).
    labels: Optional[Dict[str, str]]
        Optional free-form labels associated with the run.
    """

    run_id: str
    test_id: str
    started_at: datetime
    labels: Optional[Dict[str, str]] = None


class DomainDatasetRef(BaseModel):
    """Reference to a dataset associated with a run.

    Attributes
    ----------
    dataset_id: str
        Unique dataset identifier in the source system.
    run_id: str
        Identifier of the parent run.
    schema_uri: Optional[str]
        Optional dataset schema URI if known.
    tags: Optional[List[str]]
        Optional tags describing the dataset.
    """

    dataset_id: str
    run_id: str
    schema_uri: Optional[str] = None
    tags: Optional[List[str]] = None


class MetricPoint(BaseModel):
    """Single metric observation in canonical form.

    Attributes
    ----------
    metric_id: str
        Canonical metric identifier (e.g., "boot.time.total_ms").
    timestamp: datetime
        Observation timestamp (UTC).
    value: float
        Numeric value of the observation.
    unit: Optional[str]
        Optional unit of measurement (e.g., "ms").
    dimensions: Optional[Dict[str, str]]
        Optional dimensional breakdown (e.g., {"os_id": "rhel-9.2"}).
    source: Optional[str]
        Optional plugin/source marker that produced this observation.
    """

    metric_id: str
    timestamp: datetime
    value: float
    unit: Optional[str] = None
    dimensions: Optional[Dict[str, str]] = None
    source: Optional[str] = None


class DomainDataset(BaseModel):
    """Canonical dataset with extracted metric points.

    Attributes
    ----------
    ref: DomainDatasetRef
        Dataset reference, including identifier and schema URI.
    run: DomainRunRef
        Run reference for contextual metadata.
    metric_points: List[MetricPoint]
        Observations extracted from the dataset.
    domain_model_version: str
        Semantic version of the domain model to enable compatibility checks.
    """

    ref: DomainDatasetRef
    run: DomainRunRef
    metric_points: List[MetricPoint] = Field(default_factory=list)
    domain_model_version: str = Field("1.0.0")
