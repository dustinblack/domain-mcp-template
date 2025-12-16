"""
Statistical analysis utilities for performance data.

Provides utilities for computing descriptive statistics, confidence intervals,
trend detection, and anomaly detection. All calculations are deterministic and
performed server-side.
"""

import logging
import math
import random
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Statistics:  # pylint: disable=too-many-instance-attributes
    """
    Container for statistical metrics.

    Attributes
    ----------
    mean : float
        Average value
    median : float
        Middle value (robust to outliers)
    min : float
        Minimum value
    max : float
        Maximum value
    std_dev : float or None
        Standard deviation (absolute variability), None if < 2 samples
    cv : float or None
        Coefficient of variance (normalized variability = std_dev/mean),
        None if < 2 samples or mean is zero
    p95 : float
        95th percentile (SLA threshold)
    p99 : float
        99th percentile (high-confidence upper bound)
    percentiles : dict or None
        Custom percentiles (e.g., {"p80": 120.0, "p10": 95.0})
    count : int
        Number of samples
    """

    mean: float
    median: float
    min: float
    max: float
    std_dev: Optional[float]
    cv: Optional[float]
    p95: float
    p99: float
    percentiles: Optional[dict]
    count: int


def compute_statistics(
    samples: List[float], percentiles: Optional[List[float]] = None
) -> Optional[Statistics]:
    """
    Compute comprehensive statistical metrics from a list of samples.

    Computes statistics suitable for performance analysis. All calculations
    are deterministic and performed server-side.

    **REUSABLE FOR TWO SCENARIOS:**
    1. Within-Run Statistics: Pass samples from a single test run
       - Example: One run with 10 boot measurements [1234, 1245, ...]
       - Shows variability/consistency within that specific run

    2. Cross-Run Statistics: Pass one value from each of many runs
       - Example: 30 nightly runs, one boot time per run [1234, 1256, ...]
       - Shows typical performance and trends across runs over time

    Both scenarios use the SAME calculation code for consistency and
    determinism. Never delegate these calculations to LLM.

    Parameters
    ----------
    samples : List[float]
        Array of measurements (e.g., boot times in milliseconds).
        Can be multiple samples from ONE run OR one value from EACH of
        multiple runs.
    percentiles : List[float] or None
        Optional list of percentiles to compute (e.g., [0.50, 0.80, 0.90]).
        Values should be between 0.0 and 1.0. Always includes p95 and p99.

    Returns
    -------
    Statistics or None
        Statistics object with computed metrics, or None if samples is empty
        or invalid.

    Examples
    --------
    >>> samples = [1234.0, 1245.0, 1256.0, 1267.0, 1278.0]
    >>> stats = compute_statistics(samples)
    >>> stats.mean
    1256.0
    >>> stats.p95
    1278.0
    >>> stats = compute_statistics(samples, percentiles=[0.10, 0.80])
    >>> stats.percentiles["p10"]
    1234.0
    """
    if not samples or len(samples) == 0:
        return None

    try:
        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        mean_val = statistics.mean(samples)
        min_val = min(samples)
        max_val = max(samples)
        median_val = statistics.median(sorted_samples)

        # Compute std dev and CV only if we have 2+ samples
        std_dev = None
        cv = None
        if n >= 2:
            std_dev = statistics.stdev(samples)
            # Coefficient of variance: normalized variability (std_dev / mean)
            # Only calculate if mean is non-zero to avoid division by zero
            if mean_val > 0:
                cv = std_dev / mean_val

        # Compute default percentiles (p95, p99)
        p95_idx = int(0.95 * n)
        p95 = sorted_samples[min(p95_idx, n - 1)]

        p99_idx = int(0.99 * n)
        p99 = sorted_samples[min(p99_idx, n - 1)]

        # Compute custom percentiles if requested
        custom_percentiles = None
        if percentiles:
            custom_percentiles = {}
            for p in percentiles:
                if 0.0 <= p <= 1.0:
                    p_idx = int(p * n)
                    p_val = sorted_samples[min(p_idx, n - 1)]
                    # Format as p10, p50, p80, etc.
                    p_label = f"p{int(p * 100)}"
                    custom_percentiles[p_label] = p_val

        return Statistics(
            mean=mean_val,
            median=median_val,
            min=min_val,
            max=max_val,
            std_dev=std_dev,
            cv=cv,
            p95=p95,
            p99=p99,
            percentiles=custom_percentiles,
            count=n,
        )
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.warning(
            "statistics.compute_failed",
            extra={"error": str(e), "sample_count": len(samples)},
        )
        return None


def compute_confidence_interval(
    samples: List[float],
    confidence: float = 0.95,
    method: str = "normal",
) -> Optional[Tuple[float, float]]:
    """
    Compute confidence interval for the mean.

    Parameters
    ----------
    samples : List[float]
        Array of measurements
    confidence : float, default=0.95
        Confidence level (0.0-1.0). Common values: 0.90, 0.95, 0.99
    method : str, default="normal"
        Method to use: "normal" (assumes normal distribution, requires n>=30)
        or "bootstrap" (resampling, works for any n>=10)

    Returns
    -------
    tuple of (float, float) or None
        (lower_bound, upper_bound) for the confidence interval,
        or None if computation fails

    Examples
    --------
    >>> samples = [100.0, 102.0, 98.0, 101.0, 99.0] * 10  # 50 samples
    >>> lower, upper = compute_confidence_interval(samples, confidence=0.95)
    >>> lower < statistics.mean(samples) < upper
    True
    """
    if not samples or len(samples) < 2:
        return None

    try:
        if method == "normal":
            return _confidence_interval_normal(samples, confidence)
        if method == "bootstrap":
            return _confidence_interval_bootstrap(samples, confidence)

        # Invalid method
        logger.warning(
            "statistics.invalid_ci_method",
            extra={"method": method, "valid": ["normal", "bootstrap"]},
        )
        return None
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.warning(
            "statistics.ci_failed",
            extra={"error": str(e), "method": method},
        )
        return None


def _confidence_interval_normal(
    samples: List[float], confidence: float
) -> Optional[Tuple[float, float]]:
    """
    Compute confidence interval assuming normal distribution.

    Uses t-distribution for small samples (n < 30) and z-distribution
    for large samples (n >= 30).
    """
    n = len(samples)
    if n < 2:
        return None

    mean = statistics.mean(samples)
    std_dev = statistics.stdev(samples)
    std_error = std_dev / math.sqrt(n)

    # Use approximate z-scores for confidence levels
    # This is a simplified implementation; a full implementation would use
    # scipy.stats.t or scipy.stats.norm
    z_scores = {
        0.90: 1.645,
        0.95: 1.960,
        0.99: 2.576,
    }

    # For small samples, use slightly larger t-values
    if n < 30:
        t_adjustments = {
            0.90: 1.833,  # approximate t for df=10
            0.95: 2.228,  # approximate t for df=10
            0.99: 3.169,  # approximate t for df=10
        }
        critical_value = t_adjustments.get(confidence, z_scores.get(confidence, 1.96))
    else:
        critical_value = z_scores.get(confidence, 1.96)

    margin = critical_value * std_error
    return (mean - margin, mean + margin)


def _confidence_interval_bootstrap(
    samples: List[float], confidence: float, n_resamples: int = 1000
) -> Optional[Tuple[float, float]]:
    """
    Compute confidence interval using bootstrap resampling.

    More robust for non-normal distributions but computationally intensive.
    """
    n = len(samples)
    if n < 2:
        return None

    # Generate bootstrap samples
    bootstrap_means: List[float] = []
    for _ in range(n_resamples):
        resample = random.choices(
            samples, k=n
        )  # nosec B311 - statistical use, not crypto
        bootstrap_means.append(statistics.mean(resample))

    # Compute percentile-based confidence interval
    bootstrap_means.sort()
    alpha = 1.0 - confidence
    lower_idx = int(alpha / 2 * n_resamples)
    upper_idx = int((1.0 - alpha / 2) * n_resamples)

    return (bootstrap_means[lower_idx], bootstrap_means[upper_idx])


def detect_anomalies(
    samples: List[float],
    method: str = "iqr",
    threshold: float = 1.5,
) -> List[int]:
    """
    Detect anomalies (outliers) in a dataset.

    Parameters
    ----------
    samples : List[float]
        Array of measurements
    method : str, default="iqr"
        Detection method:
        - "iqr": Interquartile Range (robust, default)
        - "zscore": Z-score (assumes normal distribution)
        - "mad": Median Absolute Deviation (very robust)
    threshold : float, default=1.5
        Sensitivity threshold. For IQR: 1.5 is standard, 3.0 is extreme.
        For Z-score: 3.0 is standard, 2.0 is more sensitive.
        For MAD: 3.0 is standard.

    Returns
    -------
    List[int]
        Indices of anomalous samples (empty list if none found)

    Examples
    --------
    >>> samples = [100.0, 101.0, 99.0, 102.0, 500.0, 98.0]  # 500 is anomaly
    >>> anomalies = detect_anomalies(samples, method="iqr")
    >>> 4 in anomalies  # Index of 500.0
    True
    """
    if not samples or len(samples) < 3:
        return []

    try:
        if method == "iqr":
            return _detect_anomalies_iqr(samples, threshold)
        if method == "zscore":
            return _detect_anomalies_zscore(samples, threshold)
        if method == "mad":
            return _detect_anomalies_mad(samples, threshold)

        # Invalid method
        logger.warning(
            "statistics.invalid_anomaly_method",
            extra={"method": method, "valid": ["iqr", "zscore", "mad"]},
        )
        return []
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.warning(
            "statistics.anomaly_detection_failed",
            extra={"error": str(e), "method": method},
        )
        return []


def _detect_anomalies_iqr(samples: List[float], threshold: float) -> List[int]:
    """Detect anomalies using Interquartile Range method."""
    sorted_samples = sorted(samples)
    n = len(sorted_samples)

    # Compute Q1 and Q3
    q1 = sorted_samples[n // 4]
    q3 = sorted_samples[3 * n // 4]
    iqr = q3 - q1

    lower_bound = q1 - threshold * iqr
    upper_bound = q3 + threshold * iqr

    anomalies = []
    for idx, value in enumerate(samples):
        if value < lower_bound or value > upper_bound:
            anomalies.append(idx)

    return anomalies


def _detect_anomalies_zscore(samples: List[float], threshold: float) -> List[int]:
    """Detect anomalies using Z-score method."""
    if len(samples) < 2:
        return []

    mean = statistics.mean(samples)
    std_dev = statistics.stdev(samples)

    if std_dev == 0:
        return []

    anomalies = []
    for idx, value in enumerate(samples):
        z_score = abs((value - mean) / std_dev)
        if z_score > threshold:
            anomalies.append(idx)

    return anomalies


def _detect_anomalies_mad(samples: List[float], threshold: float) -> List[int]:
    """Detect anomalies using Median Absolute Deviation method."""
    median = statistics.median(samples)
    deviations = [abs(x - median) for x in samples]
    mad = statistics.median(deviations)

    if mad == 0:
        return []

    # Modified Z-score using MAD
    # Constant 1.4826 makes MAD consistent with std dev for normal distribution
    anomalies = []
    for idx, value in enumerate(samples):
        modified_z_score = 0.6745 * abs(value - median) / mad
        if modified_z_score > threshold:
            anomalies.append(idx)

    return anomalies


def detect_trend(
    values: List[float],
    timestamps: Optional[List[float]] = None,
    method: str = "linear",
) -> Optional[Tuple[str, float]]:
    """
    Detect trend in time series data.

    Parameters
    ----------
    values : List[float]
        Array of measurements (e.g., boot times over time)
    timestamps : List[float] or None
        Optional timestamps for each value. If None, uses indices 0, 1, 2, ...
    method : str, default="linear"
        Trend detection method:
        - "linear": Linear regression slope
        - "mann-kendall": Non-parametric Mann-Kendall test

    Returns
    -------
    tuple of (str, float) or None
        (trend_direction, magnitude) where:
        - trend_direction: "increasing", "decreasing", or "stable"
        - magnitude: slope (for linear) or tau statistic (for mann-kendall)
        Returns None if computation fails

    Examples
    --------
    >>> values = [100.0, 102.0, 104.0, 106.0, 108.0]  # Increasing trend
    >>> direction, magnitude = detect_trend(values, method="linear")
    >>> direction
    'increasing'
    >>> magnitude > 0
    True
    """
    if not values or len(values) < 3:
        return None

    if timestamps is None:
        timestamps = list(range(len(values)))

    if len(timestamps) != len(values):
        logger.warning(
            "statistics.trend_length_mismatch",
            extra={"values": len(values), "timestamps": len(timestamps)},
        )
        return None

    try:
        if method == "linear":
            return _detect_trend_linear(values, timestamps)
        if method == "mann-kendall":
            return _detect_trend_mann_kendall(values)

        # Invalid method
        logger.warning(
            "statistics.invalid_trend_method",
            extra={"method": method, "valid": ["linear", "mann-kendall"]},
        )
        return None
    except (ValueError, TypeError, ZeroDivisionError) as e:
        logger.warning(
            "statistics.trend_detection_failed",
            extra={"error": str(e), "method": method},
        )
        return None


def _detect_trend_linear(
    values: List[float], timestamps: List[float]
) -> Optional[Tuple[str, float]]:
    """Detect trend using linear regression."""
    n = len(values)
    if n < 2:
        return None

    # Compute slope using least squares
    x_mean = statistics.mean(timestamps)
    y_mean = statistics.mean(values)

    numerator = sum((timestamps[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((timestamps[i] - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return ("stable", 0.0)

    slope = numerator / denominator

    # Classify trend
    # Use threshold of 0.1% of mean value per time unit
    threshold = abs(y_mean * 0.001)
    if abs(slope) < threshold:
        direction = "stable"
    elif slope > 0:
        direction = "increasing"
    else:
        direction = "decreasing"

    return (direction, slope)


def _detect_trend_mann_kendall(values: List[float]) -> Optional[Tuple[str, float]]:
    """Detect trend using Mann-Kendall test."""
    n = len(values)
    if n < 3:
        return None

    # Compute Mann-Kendall S statistic
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            if values[j] > values[i]:
                s += 1
            elif values[j] < values[i]:
                s -= 1

    # Compute Kendall's tau (normalized -1 to 1)
    n_comparisons = n * (n - 1) / 2
    tau = s / n_comparisons if n_comparisons > 0 else 0.0

    # Classify trend based on tau
    # tau > 0.1: increasing, tau < -0.1: decreasing, else: stable
    if tau > 0.1:
        direction = "increasing"
    elif tau < -0.1:
        direction = "decreasing"
    else:
        direction = "stable"

    return (direction, tau)
