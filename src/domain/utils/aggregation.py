"""
Data aggregation utilities for performance metrics.

Provides utilities for aggregating multiple samples with different strategies,
handling missing data, and grouping metrics by statistic type.
"""

import logging
import statistics
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AggregationStrategy(Enum):
    """Strategy for aggregating multiple samples into a single value."""

    MEAN = "mean"  # Average of all values
    MEDIAN = "median"  # Middle value (robust to outliers)
    MIN = "min"  # Minimum value
    MAX = "max"  # Maximum value
    P95 = "p95"  # 95th percentile (SLA threshold)
    P99 = "p99"  # 99th percentile (high-confidence upper bound)
    FIRST = "first"  # First value in sequence
    LAST = "last"  # Last value in sequence
    SUM = "sum"  # Sum of all values


class MissingDataStrategy(Enum):
    """Strategy for handling missing or invalid data points."""

    SKIP = "skip"  # Skip missing values, aggregate remaining
    ZERO = "zero"  # Treat missing values as zero
    INTERPOLATE = "interpolate"  # Linear interpolation from neighbors
    FORWARD_FILL = "forward_fill"  # Use previous non-missing value
    RAISE = "raise"  # Raise error on missing data


def aggregate_samples(
    samples: List[Optional[float]],
    strategy: AggregationStrategy = AggregationStrategy.MEAN,
    missing_strategy: MissingDataStrategy = MissingDataStrategy.SKIP,
) -> Optional[float]:
    """
    Aggregate multiple samples using specified strategy.

    Parameters
    ----------
    samples : List[Optional[float]]
        Array of measurements, may contain None for missing values
    strategy : AggregationStrategy, default=MEAN
        Aggregation method to use
    missing_strategy : MissingDataStrategy, default=SKIP
        How to handle missing data

    Returns
    -------
    float or None
        Aggregated value, or None if aggregation fails or produces no valid data

    Raises
    ------
    ValueError
        If missing_strategy=RAISE and missing data is encountered

    Examples
    --------
    >>> aggregate_samples([1.0, 2.0, 3.0, 4.0, 5.0], AggregationStrategy.MEAN)
    3.0
    >>> aggregate_samples(
    ...     [1.0, None, 3.0], AggregationStrategy.MEAN, MissingDataStrategy.SKIP
    ... )
    2.0
    >>> aggregate_samples(
    ...     [1.0, None, 3.0], AggregationStrategy.MEAN, MissingDataStrategy.ZERO
    ... )
    1.33...
    """
    if not samples:
        return None

    # Handle missing data first
    processed = _handle_missing_data(samples, missing_strategy)
    if processed is None:
        return None

    # Apply aggregation strategy
    try:
        if strategy == AggregationStrategy.MEAN:
            return statistics.mean(processed)
        if strategy == AggregationStrategy.MEDIAN:
            return statistics.median(processed)
        if strategy == AggregationStrategy.MIN:
            return min(processed)
        if strategy == AggregationStrategy.MAX:
            return max(processed)
        if strategy == AggregationStrategy.P95:
            return _compute_percentile(processed, 0.95)
        if strategy == AggregationStrategy.P99:
            return _compute_percentile(processed, 0.99)
        if strategy == AggregationStrategy.FIRST:
            return processed[0] if processed else None
        if strategy == AggregationStrategy.LAST:
            return processed[-1] if processed else None
        if strategy == AggregationStrategy.SUM:
            return sum(processed)

        # Invalid strategy
        logger.warning(
            "aggregation.invalid_strategy",
            extra={"strategy": strategy.value},
        )
        return None
    except (ValueError, TypeError, IndexError) as e:
        logger.warning(
            "aggregation.failed",
            extra={"error": str(e), "strategy": strategy.value},
        )
        return None


def _handle_missing_data(
    samples: List[Optional[float]], strategy: MissingDataStrategy
) -> Optional[List[float]]:
    """Handle missing data according to strategy."""
    if strategy == MissingDataStrategy.SKIP:
        return _skip_missing(samples)
    if strategy == MissingDataStrategy.ZERO:
        return _fill_missing_with_zero(samples)
    if strategy == MissingDataStrategy.INTERPOLATE:
        return _interpolate_missing(samples)
    if strategy == MissingDataStrategy.FORWARD_FILL:
        return _forward_fill_missing(samples)
    if strategy == MissingDataStrategy.RAISE:
        return _raise_on_missing(samples)

    # Invalid strategy
    logger.warning(
        "aggregation.invalid_missing_strategy",
        extra={"strategy": strategy.value},
    )
    return None


def _skip_missing(samples: List[Optional[float]]) -> Optional[List[float]]:
    """Skip None values and return only valid samples."""
    result = [s for s in samples if s is not None]
    return result if result else None


def _fill_missing_with_zero(samples: List[Optional[float]]) -> List[float]:
    """Replace None values with 0.0."""
    return [s if s is not None else 0.0 for s in samples]


def _interpolate_missing(samples: List[Optional[float]]) -> Optional[List[float]]:
    """Interpolate missing values from neighbors."""
    if not samples:
        return None

    result = list(samples)  # Make a copy

    for i, value in enumerate(result):
        if value is not None:
            continue

        # Find previous non-None value
        prev_val = None
        prev_idx = None
        for j in range(i - 1, -1, -1):
            if result[j] is not None:
                prev_val = result[j]
                prev_idx = j
                break

        # Find next non-None value
        next_val = None
        next_idx = None
        for j in range(i + 1, len(result)):
            if result[j] is not None:
                next_val = result[j]
                next_idx = j
                break

        # Interpolate
        if (
            prev_val is not None
            and next_val is not None
            and prev_idx is not None
            and next_idx is not None
        ):
            # Linear interpolation
            total_gap = next_idx - prev_idx
            position = i - prev_idx
            result[i] = prev_val + (next_val - prev_val) * (position / total_gap)
        elif prev_val is not None:
            # Use previous value (forward fill)
            result[i] = prev_val
        elif next_val is not None:
            # Use next value (backward fill)
            result[i] = next_val
        else:
            # All values are None
            return None

    return result  # type: ignore[return-value]


def _forward_fill_missing(samples: List[Optional[float]]) -> Optional[List[float]]:
    """Forward fill missing values with previous non-None value."""
    if not samples:
        return None

    result = []
    last_valid = None

    for sample in samples:
        if sample is not None:
            last_valid = sample
            result.append(sample)
        elif last_valid is not None:
            result.append(last_valid)
        else:
            # No previous valid value, skip this one
            continue

    return result if result else None


def _raise_on_missing(samples: List[Optional[float]]) -> List[float]:
    """Raise ValueError if any missing data is found."""
    if any(s is None for s in samples):
        missing_count = sum(1 for s in samples if s is None)
        raise ValueError(
            f"Missing data encountered: {missing_count}/{len(samples)} values are None"
        )
    return [s for s in samples if s is not None]  # Type narrowing for mypy


def _compute_percentile(values: List[float], percentile: float) -> float:
    """Compute percentile from sorted values."""
    sorted_values = sorted(values)
    n = len(sorted_values)
    idx = int(percentile * n)
    return sorted_values[min(idx, n - 1)]


def group_by_statistic_type(
    label_values: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group label value items by statistic type.

    Useful for processing multi-sample data where each sample has multiple
    statistic representations (mean, p95, p99, etc.).

    Parameters
    ----------
    label_values : List[Dict[str, any]]
        List of label value items from Horreum

    Returns
    -------
    Dict[str, List[Dict]]
        Dictionary mapping statistic type (e.g., "mean", "p95") to list of items

    Examples
    --------
    >>> items = [
    ...     {"Statistic Type": "mean", "value": 100},
    ...     {"Statistic Type": "p95", "value": 120},
    ...     {"Statistic Type": "mean", "value": 105},
    ... ]
    >>> grouped = group_by_statistic_type(items)
    >>> len(grouped["mean"])
    2
    >>> len(grouped["p95"])
    1
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for item in label_values:
        # Get statistic type from label
        stat_type = item.get("Statistic Type") or item.get("statistic_type", "mean")

        # Normalize to lowercase
        stat_type = str(stat_type).lower()

        # Add to appropriate group
        if stat_type not in grouped:
            grouped[stat_type] = []
        grouped[stat_type].append(item)

    return grouped
