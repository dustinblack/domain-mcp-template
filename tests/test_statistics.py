"""
Tests for statistics utilities.
"""

import statistics as builtin_stats

from src.domain.utils.statistics import (
    Statistics,
    compute_confidence_interval,
    compute_statistics,
    detect_anomalies,
    detect_trend,
)

# ============================================================================
# compute_statistics() tests
# ============================================================================


def test_compute_statistics_basic():
    """Test compute_statistics with basic input."""
    samples = [100.0, 102.0, 98.0, 101.0, 99.0]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.mean == 100.0
    assert stats.median == 100.0
    assert stats.min == 98.0
    assert stats.max == 102.0
    assert stats.count == 5


def test_compute_statistics_single_value():
    """Test compute_statistics with single value."""
    samples = [100.0]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.mean == 100.0
    assert stats.median == 100.0
    assert stats.min == 100.0
    assert stats.max == 100.0
    assert stats.std_dev is None  # < 2 samples
    assert stats.cv is None  # < 2 samples
    assert stats.count == 1


def test_compute_statistics_two_values():
    """Test compute_statistics with two values."""
    samples = [100.0, 110.0]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.mean == 105.0
    assert stats.median == 105.0
    assert stats.std_dev is not None  # >= 2 samples
    assert stats.cv is not None  # >= 2 samples


def test_compute_statistics_std_dev():
    """Test standard deviation calculation."""
    samples = [100.0, 102.0, 98.0, 101.0, 99.0]
    stats = compute_statistics(samples)
    assert stats is not None
    expected_std = builtin_stats.stdev(samples)
    assert abs(stats.std_dev - expected_std) < 0.001


def test_compute_statistics_cv():
    """Test coefficient of variance calculation."""
    samples = [100.0, 110.0, 90.0, 105.0, 95.0]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.cv is not None
    expected_cv = builtin_stats.stdev(samples) / builtin_stats.mean(samples)
    assert abs(stats.cv - expected_cv) < 0.001


def test_compute_statistics_cv_zero_mean():
    """Test CV is None when mean is zero."""
    samples = [-10.0, 0.0, 10.0]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.mean == 0.0
    assert stats.cv is None  # CV undefined for zero mean


def test_compute_statistics_percentiles():
    """Test percentile calculations."""
    samples = list(range(1, 101))  # 1 to 100
    stats = compute_statistics([float(x) for x in samples])
    assert stats is not None
    # For 100 samples, p95 should be around 95, p99 around 99
    assert 94.0 <= stats.p95 <= 96.0
    assert 98.0 <= stats.p99 <= 100.0


def test_compute_statistics_empty_list():
    """Test compute_statistics with empty list."""
    stats = compute_statistics([])
    assert stats is None


def test_compute_statistics_none():
    """Test compute_statistics with None."""
    stats = compute_statistics(None)
    assert stats is None


def test_compute_statistics_large_dataset():
    """Test compute_statistics with large dataset."""
    samples = [float(i) for i in range(1000)]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.count == 1000
    assert stats.mean == 499.5  # Mean of 0-999


def test_compute_statistics_identical_values():
    """Test compute_statistics with all identical values."""
    samples = [100.0] * 10
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.mean == 100.0
    assert stats.std_dev == 0.0
    assert stats.cv == 0.0  # 0 / 100 = 0


def test_compute_statistics_negative_values():
    """Test compute_statistics with negative values."""
    samples = [-100.0, -102.0, -98.0, -101.0, -99.0]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.mean == -100.0
    assert stats.min == -102.0
    assert stats.max == -98.0


def test_compute_statistics_custom_percentiles():
    """Test compute_statistics with custom percentiles."""
    samples = list(range(1, 101))  # 1 to 100
    stats = compute_statistics(
        [float(x) for x in samples], percentiles=[0.10, 0.50, 0.80]
    )
    assert stats is not None
    assert "p10" in stats.percentiles
    assert "p50" in stats.percentiles
    assert "p80" in stats.percentiles
    # p50 should be around 50 for 1-100
    assert 49.0 <= stats.percentiles["p50"] <= 51.0
    # p10 should be around 10
    assert 9.0 <= stats.percentiles["p10"] <= 11.0
    # p80 should be around 80
    assert 79.0 <= stats.percentiles["p80"] <= 81.0


def test_compute_statistics_no_custom_percentiles():
    """Test that percentiles is None when not requested."""
    samples = [100.0, 102.0, 98.0]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.percentiles is None


# ============================================================================
# compute_confidence_interval() tests
# ============================================================================


def test_ci_normal_basic():
    """Test confidence interval with normal method."""
    samples = [100.0] * 20 + [102.0] * 20 + [98.0] * 20  # 60 samples
    result = compute_confidence_interval(samples, confidence=0.95, method="normal")
    assert result is not None
    lower, upper = result
    mean = builtin_stats.mean(samples)
    assert lower < mean < upper


def test_ci_normal_95():
    """Test 95% confidence interval."""
    samples = [float(i) for i in range(50, 151)]  # 50-150
    result = compute_confidence_interval(samples, confidence=0.95, method="normal")
    assert result is not None
    lower, upper = result
    # Mean is 100, interval should be symmetric
    assert lower < 100.0 < upper


def test_ci_normal_99():
    """Test 99% confidence interval (wider than 95%)."""
    samples = [float(i) for i in range(50, 151)]
    ci_95 = compute_confidence_interval(samples, confidence=0.95, method="normal")
    ci_99 = compute_confidence_interval(samples, confidence=0.99, method="normal")
    assert ci_95 is not None
    assert ci_99 is not None
    # 99% CI should be wider than 95% CI
    assert (ci_99[1] - ci_99[0]) > (ci_95[1] - ci_95[0])


def test_ci_bootstrap_basic():
    """Test confidence interval with bootstrap method."""
    samples = [100.0, 102.0, 98.0, 101.0, 99.0, 103.0, 97.0, 100.0, 101.0, 99.0]
    result = compute_confidence_interval(samples, confidence=0.95, method="bootstrap")
    assert result is not None
    lower, upper = result
    mean = builtin_stats.mean(samples)
    assert lower < mean < upper


def test_ci_empty_list():
    """Test CI with empty list."""
    result = compute_confidence_interval([])
    assert result is None


def test_ci_single_value():
    """Test CI with single value."""
    result = compute_confidence_interval([100.0])
    assert result is None


def test_ci_invalid_method():
    """Test CI with invalid method."""
    samples = [100.0, 102.0, 98.0]
    result = compute_confidence_interval(samples, method="invalid")
    assert result is None


# ============================================================================
# detect_anomalies() tests
# ============================================================================


def test_anomalies_iqr_basic():
    """Test anomaly detection with IQR method."""
    # Normal values plus outliers
    samples = [100.0, 101.0, 99.0, 102.0, 98.0, 500.0, -100.0, 103.0]
    anomalies = detect_anomalies(samples, method="iqr", threshold=1.5)
    assert 5 in anomalies  # 500.0 is outlier
    assert 6 in anomalies  # -100.0 is outlier


def test_anomalies_iqr_no_outliers():
    """Test IQR with no outliers."""
    samples = [100.0, 101.0, 99.0, 102.0, 98.0, 103.0, 97.0]
    anomalies = detect_anomalies(samples, method="iqr", threshold=1.5)
    assert len(anomalies) == 0


def test_anomalies_zscore_basic():
    """Test anomaly detection with Z-score method."""
    # Need more samples for Z-score to work well, and a clearer outlier
    samples = [100.0] * 20 + [500.0]  # 20 normal + 1 extreme outlier
    anomalies = detect_anomalies(samples, method="zscore", threshold=3.0)
    assert 20 in anomalies  # 500.0 (index 20) is extreme outlier


def test_anomalies_zscore_no_outliers():
    """Test Z-score with no outliers."""
    samples = [100.0, 101.0, 99.0, 102.0, 98.0, 103.0, 97.0]
    anomalies = detect_anomalies(samples, method="zscore", threshold=3.0)
    assert len(anomalies) == 0


def test_anomalies_mad_basic():
    """Test anomaly detection with MAD method."""
    samples = [100.0, 101.0, 99.0, 102.0, 98.0, 500.0, 103.0]
    anomalies = detect_anomalies(samples, method="mad", threshold=3.0)
    assert 5 in anomalies  # 500.0 is outlier


def test_anomalies_mad_no_outliers():
    """Test MAD with no outliers."""
    samples = [100.0, 101.0, 99.0, 102.0, 98.0, 103.0, 97.0]
    anomalies = detect_anomalies(samples, method="mad", threshold=3.0)
    assert len(anomalies) == 0


def test_anomalies_empty_list():
    """Test anomaly detection with empty list."""
    anomalies = detect_anomalies([])
    assert len(anomalies) == 0


def test_anomalies_too_few_samples():
    """Test anomaly detection with < 3 samples."""
    anomalies = detect_anomalies([100.0, 200.0])
    assert len(anomalies) == 0


def test_anomalies_invalid_method():
    """Test anomaly detection with invalid method."""
    samples = [100.0, 101.0, 500.0]
    anomalies = detect_anomalies(samples, method="invalid")
    assert len(anomalies) == 0


def test_anomalies_identical_values():
    """Test anomaly detection with identical values."""
    samples = [100.0] * 10
    anomalies = detect_anomalies(samples, method="iqr")
    assert len(anomalies) == 0


def test_anomalies_sensitivity():
    """Test anomaly sensitivity with different thresholds."""
    samples = [100.0, 101.0, 99.0, 102.0, 98.0, 110.0, 103.0]
    # More sensitive (lower threshold) should find more anomalies
    sensitive = detect_anomalies(samples, method="iqr", threshold=1.0)
    standard = detect_anomalies(samples, method="iqr", threshold=1.5)
    assert len(sensitive) >= len(standard)


# ============================================================================
# detect_trend() tests
# ============================================================================


def test_trend_linear_increasing():
    """Test trend detection with increasing values."""
    values = [100.0, 102.0, 104.0, 106.0, 108.0, 110.0]
    result = detect_trend(values, method="linear")
    assert result is not None
    direction, magnitude = result
    assert direction == "increasing"
    assert magnitude > 0


def test_trend_linear_decreasing():
    """Test trend detection with decreasing values."""
    values = [110.0, 108.0, 106.0, 104.0, 102.0, 100.0]
    result = detect_trend(values, method="linear")
    assert result is not None
    direction, magnitude = result
    assert direction == "decreasing"
    assert magnitude < 0


def test_trend_linear_stable():
    """Test trend detection with stable values."""
    values = [100.0, 100.1, 99.9, 100.0, 100.1, 99.9]
    result = detect_trend(values, method="linear")
    assert result is not None
    direction, _ = result
    assert direction == "stable"


def test_trend_linear_with_timestamps():
    """Test trend with explicit timestamps."""
    values = [100.0, 110.0, 120.0]
    timestamps = [0.0, 10.0, 20.0]
    result = detect_trend(values, timestamps=timestamps, method="linear")
    assert result is not None
    direction, _ = result
    assert direction == "increasing"


def test_trend_mann_kendall_increasing():
    """Test Mann-Kendall with increasing trend."""
    values = [100.0, 105.0, 103.0, 110.0, 108.0, 115.0]  # Overall increasing
    result = detect_trend(values, method="mann-kendall")
    assert result is not None
    direction, tau = result
    assert direction == "increasing"
    assert tau > 0


def test_trend_mann_kendall_decreasing():
    """Test Mann-Kendall with decreasing trend."""
    values = [115.0, 110.0, 112.0, 105.0, 107.0, 100.0]  # Overall decreasing
    result = detect_trend(values, method="mann-kendall")
    assert result is not None
    direction, tau = result
    assert direction == "decreasing"
    assert tau < 0


def test_trend_mann_kendall_stable():
    """Test Mann-Kendall with stable values."""
    # Use truly flat values to ensure stable classification
    values = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    result = detect_trend(values, method="mann-kendall")
    assert result is not None
    direction, _ = result
    assert direction == "stable"


def test_trend_empty_list():
    """Test trend detection with empty list."""
    result = detect_trend([])
    assert result is None


def test_trend_too_few_values():
    """Test trend detection with < 3 values."""
    result = detect_trend([100.0, 102.0])
    assert result is None


def test_trend_timestamp_mismatch():
    """Test trend with mismatched timestamps."""
    values = [100.0, 102.0, 104.0]
    timestamps = [0.0, 1.0]  # Wrong length
    result = detect_trend(values, timestamps=timestamps)
    assert result is None


def test_trend_invalid_method():
    """Test trend with invalid method."""
    values = [100.0, 102.0, 104.0]
    result = detect_trend(values, method="invalid")
    assert result is None


# ============================================================================
# Statistics dataclass tests
# ============================================================================


def test_statistics_dataclass():
    """Test Statistics dataclass creation."""
    stats = Statistics(
        mean=100.0,
        median=99.0,
        min=95.0,
        max=105.0,
        std_dev=3.0,
        cv=0.03,
        p95=104.0,
        p99=105.0,
        percentiles={"p80": 103.0},
        count=50,
    )
    assert stats.mean == 100.0
    assert stats.median == 99.0
    assert stats.min == 95.0
    assert stats.max == 105.0
    assert stats.std_dev == 3.0
    assert stats.cv == 0.03
    assert stats.p95 == 104.0
    assert stats.p99 == 105.0
    assert stats.percentiles["p80"] == 103.0
    assert stats.count == 50


def test_statistics_optional_fields():
    """Test Statistics with optional fields as None."""
    stats = Statistics(
        mean=100.0,
        median=100.0,
        min=100.0,
        max=100.0,
        std_dev=None,
        cv=None,
        p95=100.0,
        p99=100.0,
        percentiles=None,
        count=1,
    )
    assert stats.std_dev is None
    assert stats.cv is None
    assert stats.percentiles is None


# ============================================================================
# Edge cases and error handling tests
# ============================================================================


def test_compute_statistics_extreme_values():
    """Test statistics with extreme values."""
    samples = [1e-10, 1e10, 1e-5, 1e5]
    stats = compute_statistics(samples)
    assert stats is not None
    assert stats.count == 4


def test_ci_small_sample_normal():
    """Test normal CI with small sample (uses t-distribution approximation)."""
    samples = [100.0, 102.0, 98.0, 101.0, 99.0]  # n=5 < 30
    result = compute_confidence_interval(samples, confidence=0.95, method="normal")
    assert result is not None
    # Should still produce valid interval
    lower, upper = result
    assert lower < upper


def test_anomalies_all_anomalies():
    """Test when all values might be considered anomalies."""
    # Very spread out values
    samples = [1.0, 100.0, 200.0, 300.0, 400.0]
    anomalies = detect_anomalies(samples, method="iqr", threshold=0.1)
    # With very strict threshold, might detect some as anomalies
    assert isinstance(anomalies, list)


def test_trend_constant_values():
    """Test trend with all constant values."""
    values = [100.0] * 10
    result = detect_trend(values, method="linear")
    assert result is not None
    direction, magnitude = result
    assert direction == "stable"
    assert magnitude == 0.0
