"""
Tests for aggregation utilities.
"""

import pytest

from src.domain.utils.aggregation import (
    AggregationStrategy,
    MissingDataStrategy,
    aggregate_samples,
    group_by_statistic_type,
)

# ============================================================================
# aggregate_samples() tests - basic strategies
# ============================================================================


def test_aggregate_mean_basic():
    """Test mean aggregation with simple values."""
    result = aggregate_samples([1.0, 2.0, 3.0, 4.0, 5.0], AggregationStrategy.MEAN)
    assert result == 3.0


def test_aggregate_median_basic():
    """Test median aggregation."""
    result = aggregate_samples([1.0, 2.0, 3.0, 4.0, 5.0], AggregationStrategy.MEDIAN)
    assert result == 3.0


def test_aggregate_min_basic():
    """Test min aggregation."""
    result = aggregate_samples([5.0, 2.0, 8.0, 1.0, 4.0], AggregationStrategy.MIN)
    assert result == 1.0


def test_aggregate_max_basic():
    """Test max aggregation."""
    result = aggregate_samples([5.0, 2.0, 8.0, 1.0, 4.0], AggregationStrategy.MAX)
    assert result == 8.0


def test_aggregate_p95_basic():
    """Test 95th percentile aggregation."""
    values = [float(i) for i in range(1, 101)]  # 1-100
    result = aggregate_samples(values, AggregationStrategy.P95)
    assert 94.0 <= result <= 96.0


def test_aggregate_p99_basic():
    """Test 99th percentile aggregation."""
    values = [float(i) for i in range(1, 101)]  # 1-100
    result = aggregate_samples(values, AggregationStrategy.P99)
    assert 98.0 <= result <= 100.0


def test_aggregate_first_basic():
    """Test first value aggregation."""
    result = aggregate_samples([5.0, 2.0, 8.0, 1.0, 4.0], AggregationStrategy.FIRST)
    assert result == 5.0


def test_aggregate_last_basic():
    """Test last value aggregation."""
    result = aggregate_samples([5.0, 2.0, 8.0, 1.0, 4.0], AggregationStrategy.LAST)
    assert result == 4.0


def test_aggregate_sum_basic():
    """Test sum aggregation."""
    result = aggregate_samples([1.0, 2.0, 3.0, 4.0, 5.0], AggregationStrategy.SUM)
    assert result == 15.0


# ============================================================================
# Missing data handling tests
# ============================================================================


def test_aggregate_skip_missing():
    """Test SKIP strategy with missing values."""
    result = aggregate_samples(
        [1.0, None, 3.0, None, 5.0],
        AggregationStrategy.MEAN,
        MissingDataStrategy.SKIP,
    )
    assert result == 3.0  # (1+3+5)/3


def test_aggregate_zero_missing():
    """Test ZERO strategy with missing values."""
    result = aggregate_samples(
        [1.0, None, 3.0, None, 5.0],
        AggregationStrategy.MEAN,
        MissingDataStrategy.ZERO,
    )
    assert result == 1.8  # (1+0+3+0+5)/5


def test_aggregate_interpolate_missing():
    """Test INTERPOLATE strategy with missing values."""
    result = aggregate_samples(
        [1.0, None, 5.0],
        AggregationStrategy.MEAN,
        MissingDataStrategy.INTERPOLATE,
    )
    # Should interpolate middle value as 3.0: (1+3+5)/3 = 3.0
    assert result == 3.0


def test_aggregate_interpolate_multiple_missing():
    """Test INTERPOLATE with multiple consecutive missing values."""
    result = aggregate_samples(
        [1.0, None, None, 7.0],
        AggregationStrategy.MEAN,
        MissingDataStrategy.INTERPOLATE,
    )
    # Should interpolate as [1.0, 3.0, 5.0, 7.0]: mean = 4.0
    assert result == 4.0


def test_aggregate_forward_fill_missing():
    """Test FORWARD_FILL strategy."""
    result = aggregate_samples(
        [1.0, None, None, 4.0, None],
        AggregationStrategy.MEAN,
        MissingDataStrategy.FORWARD_FILL,
    )
    # Should fill as [1.0, 1.0, 1.0, 4.0, 4.0]: mean = (1+1+1+4+4)/5 = 2.2
    assert result == 2.2


def test_aggregate_raise_on_missing():
    """Test RAISE strategy throws error on missing data."""
    with pytest.raises(ValueError, match="Missing data encountered"):
        aggregate_samples(
            [1.0, None, 3.0],
            AggregationStrategy.MEAN,
            MissingDataStrategy.RAISE,
        )


def test_aggregate_raise_no_missing():
    """Test RAISE strategy works fine with no missing data."""
    result = aggregate_samples(
        [1.0, 2.0, 3.0],
        AggregationStrategy.MEAN,
        MissingDataStrategy.RAISE,
    )
    assert result == 2.0


# ============================================================================
# Edge cases
# ============================================================================


def test_aggregate_empty_list():
    """Test aggregation with empty list."""
    result = aggregate_samples([], AggregationStrategy.MEAN)
    assert result is None


def test_aggregate_all_none():
    """Test aggregation when all values are None."""
    result = aggregate_samples([None, None, None], AggregationStrategy.MEAN)
    assert result is None


def test_aggregate_single_value():
    """Test aggregation with single value."""
    result = aggregate_samples([42.0], AggregationStrategy.MEAN)
    assert result == 42.0


def test_aggregate_single_value_with_none():
    """Test aggregation with single valid value and Nones."""
    result = aggregate_samples(
        [None, 42.0, None], AggregationStrategy.MEAN, MissingDataStrategy.SKIP
    )
    assert result == 42.0


def test_aggregate_identical_values():
    """Test aggregation with all identical values."""
    result = aggregate_samples([5.0, 5.0, 5.0, 5.0], AggregationStrategy.MEAN)
    assert result == 5.0


def test_aggregate_negative_values():
    """Test aggregation with negative values."""
    result = aggregate_samples([-5.0, -2.0, -8.0, -1.0, -4.0], AggregationStrategy.MEAN)
    assert result == -4.0


def test_aggregate_mixed_positive_negative():
    """Test aggregation with mixed positive and negative values."""
    result = aggregate_samples([-2.0, -1.0, 0.0, 1.0, 2.0], AggregationStrategy.MEAN)
    assert result == 0.0


def test_aggregate_interpolate_missing_at_start():
    """Test interpolation when missing values are at start."""
    result = aggregate_samples(
        [None, None, 5.0, 7.0],
        AggregationStrategy.MEAN,
        MissingDataStrategy.INTERPOLATE,
    )
    # Should fill as [5.0, 5.0, 5.0, 7.0] (backward fill for start)
    assert result == 5.5


def test_aggregate_interpolate_missing_at_end():
    """Test interpolation when missing values are at end."""
    result = aggregate_samples(
        [1.0, 3.0, None, None],
        AggregationStrategy.MEAN,
        MissingDataStrategy.INTERPOLATE,
    )
    # Should fill as [1.0, 3.0, 3.0, 3.0] (forward fill for end)
    assert result == 2.5


def test_aggregate_forward_fill_missing_at_start():
    """Test forward fill when missing values are at start (should skip)."""
    result = aggregate_samples(
        [None, None, 3.0, 4.0],
        AggregationStrategy.MEAN,
        MissingDataStrategy.FORWARD_FILL,
    )
    # Should skip initial Nones: [3.0, 4.0]
    assert result == 3.5


# ============================================================================
# group_by_statistic_type() tests
# ============================================================================


def test_group_by_statistic_type_basic():
    """Test grouping by statistic type."""
    items = [
        {"Statistic Type": "mean", "value": 100},
        {"Statistic Type": "p95", "value": 120},
        {"Statistic Type": "mean", "value": 105},
        {"Statistic Type": "p99", "value": 130},
    ]
    grouped = group_by_statistic_type(items)

    assert len(grouped["mean"]) == 2
    assert len(grouped["p95"]) == 1
    assert len(grouped["p99"]) == 1


def test_group_by_statistic_type_lowercase():
    """Test that statistic types are normalized to lowercase."""
    items = [
        {"Statistic Type": "MEAN", "value": 100},
        {"Statistic Type": "Mean", "value": 105},
        {"Statistic Type": "mean", "value": 110},
    ]
    grouped = group_by_statistic_type(items)

    assert len(grouped["mean"]) == 3


def test_group_by_statistic_type_alternative_key():
    """Test grouping with alternative key name (statistic_type)."""
    items = [
        {"statistic_type": "mean", "value": 100},
        {"statistic_type": "p95", "value": 120},
    ]
    grouped = group_by_statistic_type(items)

    assert len(grouped["mean"]) == 1
    assert len(grouped["p95"]) == 1


def test_group_by_statistic_type_missing_key():
    """Test grouping when statistic type is missing (defaults to mean)."""
    items = [
        {"value": 100},
        {"Statistic Type": "p95", "value": 120},
    ]
    grouped = group_by_statistic_type(items)

    assert len(grouped["mean"]) == 1
    assert len(grouped["p95"]) == 1


def test_group_by_statistic_type_empty_list():
    """Test grouping with empty list."""
    grouped = group_by_statistic_type([])
    assert not grouped


def test_group_by_statistic_type_preserves_data():
    """Test that grouping preserves all item data."""
    items = [
        {"Statistic Type": "mean", "value": 100, "other": "data1"},
        {"Statistic Type": "mean", "value": 105, "other": "data2"},
    ]
    grouped = group_by_statistic_type(items)

    assert grouped["mean"][0]["other"] == "data1"
    assert grouped["mean"][1]["other"] == "data2"


# ============================================================================
# Integration tests
# ============================================================================


def test_aggregate_strategies_consistency():
    """Test that different strategies produce sensible relative results."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    min_val = aggregate_samples(values, AggregationStrategy.MIN)
    mean_val = aggregate_samples(values, AggregationStrategy.MEAN)
    median_val = aggregate_samples(values, AggregationStrategy.MEDIAN)
    max_val = aggregate_samples(values, AggregationStrategy.MAX)

    # Check relative ordering
    assert min_val < mean_val < max_val
    assert min_val < median_val < max_val
    assert mean_val == median_val  # For symmetric distribution


def test_aggregate_percentiles_ordering():
    """Test that percentiles are properly ordered."""
    values = [float(i) for i in range(1, 101)]

    p95 = aggregate_samples(values, AggregationStrategy.P95)
    p99 = aggregate_samples(values, AggregationStrategy.P99)
    max_val = aggregate_samples(values, AggregationStrategy.MAX)

    # p95 < p99 <= max
    assert p95 < p99
    assert p99 <= max_val


def test_aggregate_missing_strategies_comparison():
    """Test different missing data strategies produce different results."""
    values = [1.0, None, 5.0, None, 10.0]  # Changed to make strategies differ

    skip = aggregate_samples(values, AggregationStrategy.MEAN, MissingDataStrategy.SKIP)
    zero = aggregate_samples(values, AggregationStrategy.MEAN, MissingDataStrategy.ZERO)
    interpolate = aggregate_samples(
        values, AggregationStrategy.MEAN, MissingDataStrategy.INTERPOLATE
    )

    # skip: (1+5+10)/3 = 5.33
    # zero: (1+0+5+0+10)/5 = 3.2
    # interpolate: (1+3+5+7.5+10)/5 = 5.3

    # All should be different
    assert skip != zero
    assert skip != interpolate
    assert zero != interpolate

    # Zero should have lowest mean (includes zeros)
    assert zero < skip
    assert zero < interpolate


def test_first_last_consistency():
    """Test FIRST and LAST strategies are consistent."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]

    first = aggregate_samples(values, AggregationStrategy.FIRST)
    last = aggregate_samples(values, AggregationStrategy.LAST)

    assert first == values[0]
    assert last == values[-1]
    assert first < last


def test_sum_vs_mean_relationship():
    """Test that SUM = MEAN * count."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    sum_val = aggregate_samples(values, AggregationStrategy.SUM)
    mean_val = aggregate_samples(values, AggregationStrategy.MEAN)

    assert abs(sum_val - (mean_val * len(values))) < 0.001
