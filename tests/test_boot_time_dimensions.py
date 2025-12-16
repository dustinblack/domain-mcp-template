"""
Test boot time plugin dimension extraction.

Tests that MetricPoint dimensions are correctly populated from label names
and values (statistic_type, os_id, mode).
"""

import pytest

from src.domain.plugins.boot_time import BootTimePlugin


@pytest.mark.asyncio
async def test_dimension_extraction_from_production_fixture():
    """Test that dimensions are extracted from production label values."""
    import json
    from pathlib import Path

    # Load production fixture
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "boot-time"
        / "run_120214_label_values.json"
    )
    with open(fixture_path, "r") as f:
        fixture = json.load(f)

    plugin = BootTimePlugin()
    metrics = await plugin.extract(
        json_body={},
        refs={"run_id": "120214", "dataset_id": "327697"},
        label_values=fixture["items"],
    )

    # All metrics should have dimensions
    assert len(metrics) > 0, "Should extract some metrics"
    metrics_with_dims = [m for m in metrics if m.dimensions]
    assert len(metrics_with_dims) == len(metrics), "All metrics should have dimensions"

    # All metrics should have all three dimension fields
    for m in metrics:
        assert m.dimensions is not None, f"Metric {m.metric_id} missing dimensions"
        assert (
            "statistic_type" in m.dimensions
        ), f"Metric {m.metric_id} missing statistic_type"
        assert "os_id" in m.dimensions, f"Metric {m.metric_id} missing os_id"
        assert "mode" in m.dimensions, f"Metric {m.metric_id} missing mode"

    # Check expected dimension values from production data
    # All metrics from run 120214 should have these values
    for m in metrics:
        assert m.dimensions["os_id"] == "autosd", "Expected os_id=autosd"
        assert m.dimensions["mode"] == "package", "Expected mode=package"
        assert m.dimensions["statistic_type"] in [
            "average",
            "confidence",
        ], "Expected average or confidence"

    # Check that we can distinguish metrics by dimensions
    # Group by metric_id
    by_metric_id = {}
    for m in metrics:
        if m.metric_id not in by_metric_id:
            by_metric_id[m.metric_id] = []
        by_metric_id[m.metric_id].append(m)

    # For metrics with multiple instances, verify they have different dimensions
    for metric_id, ms in by_metric_id.items():
        if len(ms) > 1:
            # Get unique dimension combinations
            unique_dims = set()
            for m in ms:
                dims_tuple = tuple(sorted(m.dimensions.items()))
                unique_dims.add(dims_tuple)

            # Most metrics should have unique dimensions
            # (Some may have legitimate duplicates like userspace vs kernel timestamps)
            assert len(unique_dims) >= len(ms) // 2, (
                f"Metric {metric_id} has {len(ms)} instances but only "
                f"{len(unique_dims)} unique dimension sets"
            )


@pytest.mark.asyncio
async def test_statistic_type_extraction():
    """Test that statistic type is correctly extracted from label names."""
    plugin = BootTimePlugin()

    # Test with label values containing different statistic types
    label_values = [
        {
            "values": [
                {
                    "name": "BOOT0 - SystemInit Duration Average ms",
                    "value": 1530.286,
                },
                {
                    "name": "BOOT0 - SystemInit Duration Confidence",
                    "value": 1.948,
                },
            ],
            "run_id": "test",
            "dataset_id": "test",
            "start": "2025-10-10T00:00:00Z",
            "stop": "2025-10-10T00:01:00Z",
        }
    ]

    metrics = await plugin.extract(
        json_body={}, refs={"run_id": "test"}, label_values=label_values
    )

    # Now returns 4 metrics: 2 phases + 2 calculated totals
    assert len(metrics) == 4, "Should extract 4 metrics (2 phases + 2 totals)"

    # Find average and confidence phase metrics (not totals)
    phase_metrics = [m for m in metrics if "phase" in m.metric_id]
    assert len(phase_metrics) == 2, "Should have 2 phase metrics"

    average_metric = next(
        (m for m in phase_metrics if m.dimensions["statistic_type"] == "average"), None
    )
    confidence_metric = next(
        (m for m in phase_metrics if m.dimensions["statistic_type"] == "confidence"),
        None,
    )

    assert average_metric is not None, "Should have average metric"
    assert confidence_metric is not None, "Should have confidence metric"

    assert average_metric.value == 1530.286, "Average metric should have correct value"
    assert (
        confidence_metric.value == 1.948
    ), "Confidence metric should have correct value"


@pytest.mark.asyncio
async def test_os_id_and_mode_extraction():
    """Test that os_id and mode are extracted from labels."""
    plugin = BootTimePlugin()

    label_values = [
        {
            "values": [
                {"name": "RHIVOS OS ID", "value": "rhel"},
                {"name": "RHIVOS Mode", "value": "standard"},
                {
                    "name": "BOOT0 - SystemInit Duration Average ms",
                    "value": 1500.0,
                },
            ],
            "run_id": "test",
            "dataset_id": "test",
            "start": "2025-10-10T00:00:00Z",
        }
    ]

    metrics = await plugin.extract(
        json_body={}, refs={"run_id": "test"}, label_values=label_values
    )

    # Now returns 2 metrics: 1 phase + 1 calculated total
    assert len(metrics) == 2, "Should extract 2 metrics (1 phase + 1 total)"

    # Check the phase metric
    phase_metric = next((m for m in metrics if "phase" in m.metric_id), None)
    assert phase_metric is not None, "Should have phase metric"
    metric = phase_metric

    assert metric.dimensions is not None, "Should have dimensions"
    assert metric.dimensions["os_id"] == "rhel", "Should extract os_id=rhel"
    assert metric.dimensions["mode"] == "standard", "Should extract mode=standard"
    assert (
        metric.dimensions["statistic_type"] == "average"
    ), "Should extract statistic_type"


@pytest.mark.asyncio
async def test_dimensions_allow_filtering():
    """Test that dimensions enable filtering by os_id and mode."""
    plugin = BootTimePlugin()

    # Create label values with different OS IDs
    label_values = [
        {
            "values": [
                {"name": "RHIVOS OS ID", "value": "rhel"},
                {"name": "RHIVOS Mode", "value": "standard"},
                {"name": "BOOT0 - SystemInit Duration Average ms", "value": 1500.0},
            ],
            "run_id": "test1",
            "dataset_id": "test1",
            "start": "2025-10-10T00:00:00Z",
        },
        {
            "values": [
                {"name": "RHIVOS OS ID", "value": "autosd"},
                {"name": "RHIVOS Mode", "value": "package"},
                {"name": "BOOT0 - SystemInit Duration Average ms", "value": 1600.0},
            ],
            "run_id": "test2",
            "dataset_id": "test2",
            "start": "2025-10-10T00:00:00Z",
        },
    ]

    metrics = await plugin.extract(
        json_body={}, refs={"run_id": "test"}, label_values=label_values
    )

    # Now returns 4 metrics: 2 phases + 2 calculated totals (one for each run)
    assert len(metrics) == 4, "Should extract 4 metrics (2 phases + 2 totals)"

    # Filter by os_id
    rhel_metrics = [m for m in metrics if m.dimensions["os_id"] == "rhel"]
    autosd_metrics = [m for m in metrics if m.dimensions["os_id"] == "autosd"]

    # Each OS now has 2 metrics: 1 phase + 1 total
    assert len(rhel_metrics) == 2, "Should have 2 rhel metrics (phase + total)"
    assert len(autosd_metrics) == 2, "Should have 2 autosd metrics (phase + total)"

    # Check the phase metrics
    rhel_phase = next((m for m in rhel_metrics if "phase" in m.metric_id), None)
    autosd_phase = next((m for m in autosd_metrics if "phase" in m.metric_id), None)

    assert rhel_phase.value == 1500.0, "RHEL metric should have correct value"
    assert autosd_phase.value == 1600.0, "AutoSD metric should have correct value"

    # Filter by mode
    standard_metrics = [m for m in metrics if m.dimensions["mode"] == "standard"]
    package_metrics = [m for m in metrics if m.dimensions["mode"] == "package"]

    # Each mode now has 2 metrics: 1 phase + 1 total
    assert len(standard_metrics) == 2, "Should have 2 standard mode metrics"
    assert len(package_metrics) == 2, "Should have 2 package mode metrics"
