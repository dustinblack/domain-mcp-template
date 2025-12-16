"""Tests for data source merging strategies (Phase 3.1).

Tests verify that merge strategies correctly fetch from label values and/or
datasets, perform de-duplication, and handle error cases appropriately.
"""

# pylint: disable=redefined-outer-name

from datetime import datetime, timezone
from typing import List

import pytest

from src.domain.models import MetricPoint
from src.schemas.source_mcp_contract import MergeStrategy
from src.server.http import _merge_metric_points


@pytest.fixture
def sample_label_points() -> List[MetricPoint]:
    """Sample metrics from label values (aggregated)."""
    ts1 = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2025, 10, 9, 13, 0, 0, tzinfo=timezone.utc)
    return [
        MetricPoint(
            metric_id="boot.time.total_ms",
            timestamp=ts1,
            value=5000.0,
            unit="ms",
            source="boot-time-verbose",
        ),
        MetricPoint(
            metric_id="boot.phase.kernel_ms",
            timestamp=ts1,
            value=1000.0,
            unit="ms",
            source="boot-time-verbose",
        ),
        MetricPoint(
            metric_id="boot.time.total_ms",
            timestamp=ts2,
            value=5100.0,
            unit="ms",
            source="boot-time-verbose",
        ),
    ]


@pytest.fixture
def sample_dataset_points() -> List[MetricPoint]:
    """Sample metrics from datasets (detailed)."""
    ts1 = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    ts3 = datetime(2025, 10, 9, 14, 0, 0, tzinfo=timezone.utc)
    return [
        MetricPoint(
            metric_id="boot.time.total_ms",
            timestamp=ts1,
            value=4950.0,  # Slightly different from label value
            unit="ms",
            source="boot-time-verbose",
        ),
        MetricPoint(
            metric_id="boot.timestamp.first_service_ms",
            timestamp=ts1,
            value=3500.0,
            unit="ms",
            source="boot-time-verbose",
        ),
        MetricPoint(
            metric_id="boot.time.total_ms",
            timestamp=ts3,
            value=5200.0,
            unit="ms",
            source="boot-time-verbose",
        ),
    ]


def test_merge_prefer_fast_with_labels(sample_label_points, sample_dataset_points):
    """PREFER_FAST returns label points when available, ignores datasets."""
    result = _merge_metric_points(
        sample_label_points,
        sample_dataset_points,
        MergeStrategy.PREFER_FAST,
    )

    # Should return only label points
    assert len(result) == 3
    assert result == sample_label_points
    assert all(p in sample_label_points for p in result)


def test_merge_prefer_fast_without_labels(sample_dataset_points):
    """PREFER_FAST returns dataset points when labels are empty."""
    result = _merge_metric_points(
        [],  # No label points
        sample_dataset_points,
        MergeStrategy.PREFER_FAST,
    )

    # Should return dataset points as fallback
    assert len(result) == 3
    assert result == sample_dataset_points


def test_merge_prefer_fast_both_empty():
    """PREFER_FAST returns empty list when both sources are empty."""
    result = _merge_metric_points(
        [],
        [],
        MergeStrategy.PREFER_FAST,
    )

    assert result == []


def test_merge_comprehensive(sample_label_points, sample_dataset_points):
    """COMPREHENSIVE merges both sources with de-duplication."""
    result = _merge_metric_points(
        sample_label_points,
        sample_dataset_points,
        MergeStrategy.COMPREHENSIVE,
    )

    # Should have unique metrics from both sources
    # - boot.time.total_ms at ts1: label value wins (5000.0 not 4950.0)
    # - boot.phase.kernel_ms at ts1: from labels only
    # - boot.time.total_ms at ts2: from labels only
    # - boot.timestamp.first_service_ms at ts1: from datasets only
    # - boot.time.total_ms at ts3: from datasets only
    assert len(result) == 5  # 3 unique from labels + 2 unique from datasets

    # Verify de-duplication: label value wins for ts1
    boot_time_ts1 = [
        p
        for p in result
        if p.metric_id == "boot.time.total_ms" and p.timestamp.hour == 12
    ]
    assert len(boot_time_ts1) == 1
    assert boot_time_ts1[0].value == 5000.0  # Label value, not dataset value

    # Verify unique from datasets
    first_service = [
        p for p in result if p.metric_id == "boot.timestamp.first_service_ms"
    ]
    assert len(first_service) == 1
    assert first_service[0].value == 3500.0


def test_merge_comprehensive_sorted(sample_label_points, sample_dataset_points):
    """COMPREHENSIVE returns results sorted by timestamp then metric_id."""
    result = _merge_metric_points(
        sample_label_points,
        sample_dataset_points,
        MergeStrategy.COMPREHENSIVE,
    )

    # Verify sorted by timestamp
    timestamps = [p.timestamp for p in result]
    assert timestamps == sorted(timestamps)

    # Verify points with same timestamp are sorted by metric_id
    ts1_points = [p for p in result if p.timestamp.hour == 12]
    metric_ids = [p.metric_id for p in ts1_points]
    assert metric_ids == sorted(metric_ids)


def test_merge_comprehensive_label_precedence():
    """COMPREHENSIVE gives label values precedence over dataset values."""
    ts = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)

    label_points = [
        MetricPoint(
            metric_id="boot.time.total_ms",
            timestamp=ts,
            value=5000.0,  # Label value
            unit="ms",
            source="boot-time-verbose",
        ),
    ]

    dataset_points = [
        MetricPoint(
            metric_id="boot.time.total_ms",
            timestamp=ts,
            value=4900.0,  # Dataset value (different)
            unit="ms",
            source="boot-time-verbose",
        ),
    ]

    result = _merge_metric_points(
        label_points,
        dataset_points,
        MergeStrategy.COMPREHENSIVE,
    )

    # Should have exactly one point
    assert len(result) == 1
    # Should use label value (higher quality)
    assert result[0].value == 5000.0


def test_merge_labels_only_with_data(sample_label_points):
    """LABELS_ONLY returns label points when available."""
    result = _merge_metric_points(
        sample_label_points,
        [],  # No dataset points
        MergeStrategy.LABELS_ONLY,
    )

    assert len(result) == 3
    assert result == sample_label_points


def test_merge_labels_only_empty():
    """LABELS_ONLY returns empty list (server handles validation)."""
    # Note: The server validates LABELS_ONLY and raises ValueError
    # This function just returns empty if no labels
    result = _merge_metric_points(
        [],
        [],
        MergeStrategy.LABELS_ONLY,
    )

    assert result == []


def test_merge_datasets_only(sample_dataset_points):
    """DATASETS_ONLY returns dataset points, ignores labels."""
    result = _merge_metric_points(
        [],  # No label points (would be ignored anyway)
        sample_dataset_points,
        MergeStrategy.DATASETS_ONLY,
    )

    assert len(result) == 3
    assert result == sample_dataset_points


def test_merge_datasets_only_ignores_labels(sample_label_points, sample_dataset_points):
    """DATASETS_ONLY ignores label points even if present."""
    result = _merge_metric_points(
        sample_label_points,  # Present but should be ignored
        sample_dataset_points,
        MergeStrategy.DATASETS_ONLY,
    )

    # Should return only dataset points
    assert len(result) == 3
    assert result == sample_dataset_points
    assert all(p in sample_dataset_points for p in result)


def test_merge_preserves_dimensions():
    """Merge preserves metric dimensions."""
    ts = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)

    label_points = [
        MetricPoint(
            metric_id="boot.time.total_ms",
            timestamp=ts,
            value=5000.0,
            unit="ms",
            dimensions={"os_id": "rhel", "mode": "ridesx4"},
            source="boot-time-verbose",
        ),
    ]

    result = _merge_metric_points(
        label_points,
        [],
        MergeStrategy.PREFER_FAST,
    )

    assert len(result) == 1
    assert result[0].dimensions == {"os_id": "rhel", "mode": "ridesx4"}


def test_merge_empty_sources_all_strategies():
    """All strategies handle empty sources gracefully."""
    for strategy in MergeStrategy:
        result = _merge_metric_points([], [], strategy)
        assert result == [], f"Strategy {strategy} should return empty list"


def test_merge_comprehensive_no_duplicates():
    """COMPREHENSIVE with no overlapping metrics merges cleanly."""
    ts = datetime(2025, 10, 9, 12, 0, 0, tzinfo=timezone.utc)

    label_points = [
        MetricPoint(
            metric_id="boot.phase.kernel_ms",
            timestamp=ts,
            value=1000.0,
            unit="ms",
            source="boot-time-verbose",
        ),
    ]

    dataset_points = [
        MetricPoint(
            metric_id="boot.timestamp.first_service_ms",
            timestamp=ts,
            value=3500.0,
            unit="ms",
            source="boot-time-verbose",
        ),
    ]

    result = _merge_metric_points(
        label_points,
        dataset_points,
        MergeStrategy.COMPREHENSIVE,
    )

    # Should have both metrics
    assert len(result) == 2
    metric_ids = {p.metric_id for p in result}
    assert metric_ids == {"boot.phase.kernel_ms", "boot.timestamp.first_service_ms"}
