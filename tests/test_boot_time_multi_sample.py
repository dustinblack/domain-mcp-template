"""Tests for multi-sample boot time data handling."""

import pytest

from src.domain.plugins.boot_time import BootTimePlugin


@pytest.mark.asyncio
async def test_multi_sample_boot_time_extraction():
    """Test that multi-sample boot_time arrays are properly handled with statistics."""
    plugin = BootTimePlugin()

    # Multi-sample dataset with boot_time as array of measurements
    dataset = {
        "$schema": "urn:boot-time-verbose:06",
        "boot_time": [12345.6, 12456.7, 12234.5, 12389.2, 12412.8],
        "config": {"os_id": "rhel", "mode": "standard"},
    }

    points = await plugin.extract(dataset, refs={})

    # Should have statistical metrics plus the primary metric
    assert len(points) > 1, "Should return multiple metric points for multi-sample data"

    # Check that we have the expected metric IDs
    metric_ids = {p.metric_id for p in points}
    expected_metrics = {
        "boot.time.total_ms",  # Primary (mean)
        "boot.time.total_ms.mean",
        "boot.time.total_ms.median",
        "boot.time.total_ms.p95",
        "boot.time.total_ms.p99",
        "boot.time.total_ms.min",
        "boot.time.total_ms.max",
    }

    # std_dev is optional (requires 2+ samples)
    assert expected_metrics.issubset(
        metric_ids
    ), f"Missing expected metrics. Got: {metric_ids}"

    # Verify the values are reasonable
    mean_point = next(p for p in points if p.metric_id == "boot.time.total_ms.mean")
    min_point = next(p for p in points if p.metric_id == "boot.time.total_ms.min")
    max_point = next(p for p in points if p.metric_id == "boot.time.total_ms.max")

    assert min_point.value == 12234.5
    assert max_point.value == 12456.7
    assert 12200 < mean_point.value < 12500  # Mean should be in this range

    # Check dimensions are preserved
    assert mean_point.dimensions == {"os_id": "rhel", "mode": "standard"}


@pytest.mark.asyncio
async def test_single_sample_still_works():
    """Test that single-sample datasets still work correctly."""
    plugin = BootTimePlugin()

    # Single-sample dataset (structured format)
    dataset = {
        "$schema": "urn:boot-time-verbose:06",
        "boot_time": [
            {
                "boot_logs": [
                    {"activated": 5000, "name": "some-service"},
                    {"activated": 12345, "name": "final-service"},
                ]
            }
        ],
        "start_time": "2025-10-08T10:00:00Z",
        "end_time": "2025-10-08T10:00:12Z",
        "config": {"os_id": "rhel", "mode": "standard"},
    }

    points = await plugin.extract(dataset, refs={})

    # Should have only one metric point for single-sample data
    assert len(points) == 1
    assert points[0].metric_id == "boot.time.total_ms"
    assert points[0].value > 0


@pytest.mark.asyncio
async def test_statistics_computation():
    """Test that statistics are computed correctly."""
    plugin = BootTimePlugin()

    samples = [100.0, 200.0, 300.0, 400.0, 500.0]
    stats = plugin._compute_statistics(samples)

    assert stats["mean"] == 300.0
    assert stats["median"] == 300.0
    assert stats["min"] == 100.0
    assert stats["max"] == 500.0
    assert stats["p95"] == 500.0  # 95th percentile of 5 samples
    assert stats["p99"] == 500.0  # 99th percentile of 5 samples
    assert "std_dev" in stats  # Should have std dev for 5 samples
