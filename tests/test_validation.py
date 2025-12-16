"""
Tests for validation utilities.
"""

import logging
import math

from src.domain.utils.validation import (
    filter_valid_floats,
    is_valid_float,
    sanitize_float,
)


def test_is_valid_float_with_normal_values():
    """Test is_valid_float with normal finite values."""
    assert is_valid_float(0.0) is True
    assert is_valid_float(1.0) is True
    assert is_valid_float(-1.0) is True
    assert is_valid_float(42.5) is True
    assert is_valid_float(1000000.0) is True
    assert is_valid_float(-1000000.0) is True
    assert is_valid_float(0.000001) is True


def test_is_valid_float_with_infinity():
    """Test is_valid_float with infinity values."""
    assert is_valid_float(float("inf")) is False
    assert is_valid_float(float("-inf")) is False
    assert is_valid_float(math.inf) is False
    assert is_valid_float(-math.inf) is False


def test_is_valid_float_with_nan():
    """Test is_valid_float with NaN values."""
    assert is_valid_float(float("nan")) is False
    assert is_valid_float(math.nan) is False


def test_is_valid_float_edge_cases():
    """Test is_valid_float with edge case values."""
    # Very large but finite numbers
    assert is_valid_float(1e308) is True
    assert is_valid_float(-1e308) is True
    # Very small but finite numbers
    assert is_valid_float(1e-308) is True
    assert is_valid_float(-1e-308) is True
    # Zero variants
    assert is_valid_float(0.0) is True
    assert is_valid_float(-0.0) is True


def test_sanitize_float_with_valid_values():
    """Test sanitize_float with valid input."""
    assert sanitize_float(42.5) == 42.5
    assert sanitize_float(0.0) == 0.0
    assert sanitize_float(-10.5) == -10.5
    assert sanitize_float(1000.0) == 1000.0


def test_sanitize_float_with_infinity():
    """Test sanitize_float with infinity values."""
    assert sanitize_float(float("inf")) is None
    assert sanitize_float(float("-inf")) is None
    assert sanitize_float(float("inf"), default=0.0) == 0.0
    assert sanitize_float(float("-inf"), default=-999.0) == -999.0


def test_sanitize_float_with_nan():
    """Test sanitize_float with NaN values."""
    assert sanitize_float(float("nan")) is None
    assert sanitize_float(float("nan"), default=0.0) == 0.0


def test_sanitize_float_with_min_value():
    """Test sanitize_float with minimum value constraint."""
    assert sanitize_float(50.0, min_value=0.0) == 50.0
    assert sanitize_float(0.0, min_value=0.0) == 0.0
    assert sanitize_float(-10.0, min_value=0.0) is None
    assert sanitize_float(-10.0, min_value=0.0, default=0.0) == 0.0


def test_sanitize_float_with_max_value():
    """Test sanitize_float with maximum value constraint."""
    assert sanitize_float(50.0, max_value=100.0) == 50.0
    assert sanitize_float(100.0, max_value=100.0) == 100.0
    assert sanitize_float(150.0, max_value=100.0) is None
    assert sanitize_float(150.0, max_value=100.0, default=100.0) == 100.0


def test_sanitize_float_with_range():
    """Test sanitize_float with both min and max constraints."""
    assert sanitize_float(50.0, min_value=0.0, max_value=100.0) == 50.0
    assert sanitize_float(0.0, min_value=0.0, max_value=100.0) == 0.0
    assert sanitize_float(100.0, min_value=0.0, max_value=100.0) == 100.0
    assert sanitize_float(-10.0, min_value=0.0, max_value=100.0) is None
    assert sanitize_float(150.0, min_value=0.0, max_value=100.0) is None
    assert sanitize_float(-10.0, min_value=0.0, max_value=100.0, default=0.0) == 0.0
    assert sanitize_float(150.0, min_value=0.0, max_value=100.0, default=100.0) == 100.0


def test_sanitize_float_with_negative_range():
    """Test sanitize_float with negative ranges."""
    assert sanitize_float(-50.0, min_value=-100.0, max_value=-10.0) == -50.0
    assert sanitize_float(-5.0, min_value=-100.0, max_value=-10.0) is None
    assert sanitize_float(-150.0, min_value=-100.0, max_value=-10.0) is None


def test_filter_valid_floats_all_valid():
    """Test filter_valid_floats with all valid values."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == values
    assert invalid_count == 0


def test_filter_valid_floats_with_infinity():
    """Test filter_valid_floats with infinity values."""
    values = [1.0, float("inf"), 3.0, float("-inf"), 5.0]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == [1.0, 3.0, 5.0]
    assert invalid_count == 2


def test_filter_valid_floats_with_nan():
    """Test filter_valid_floats with NaN values."""
    values = [1.0, 2.0, float("nan"), 4.0, 5.0]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == [1.0, 2.0, 4.0, 5.0]
    assert invalid_count == 1


def test_filter_valid_floats_mixed_invalid():
    """Test filter_valid_floats with mix of invalid values."""
    values = [1.0, float("inf"), float("nan"), 4.0, float("-inf"), 6.0]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == [1.0, 4.0, 6.0]
    assert invalid_count == 3


def test_filter_valid_floats_all_invalid():
    """Test filter_valid_floats with all invalid values."""
    values = [float("inf"), float("nan"), float("-inf")]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert not filtered
    assert invalid_count == 3


def test_filter_valid_floats_empty_list():
    """Test filter_valid_floats with empty list."""
    values = []
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert not filtered
    assert invalid_count == 0


def test_filter_valid_floats_preserves_order():
    """Test that filter_valid_floats preserves original order."""
    values = [5.0, 3.0, float("inf"), 1.0, float("nan"), 4.0, 2.0]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == [5.0, 3.0, 1.0, 4.0, 2.0]
    assert invalid_count == 2


def test_filter_valid_floats_with_zeros():
    """Test filter_valid_floats with zero values."""
    values = [0.0, -0.0, 1.0, float("inf"), 0.0]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == [0.0, -0.0, 1.0, 0.0]
    assert invalid_count == 1


def test_filter_valid_floats_with_very_large_numbers():
    """Test filter_valid_floats with very large but finite numbers."""
    values = [1e308, -1e308, float("inf"), 1e100]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == [1e308, -1e308, 1e100]
    assert invalid_count == 1


def test_filter_valid_floats_with_very_small_numbers():
    """Test filter_valid_floats with very small but finite numbers."""
    values = [1e-308, -1e-308, float("nan"), 1e-100]
    filtered, invalid_count = filter_valid_floats(values, log_invalid=False)
    assert filtered == [1e-308, -1e-308, 1e-100]
    assert invalid_count == 1


def test_filter_valid_floats_logging_enabled(caplog):
    """Test that filter_valid_floats logs warnings when enabled."""
    caplog.set_level(logging.WARNING)

    values = [1.0, float("inf"), float("nan")]
    filter_valid_floats(values, log_invalid=True, log_context="test_context")

    # Should have logged 2 warnings (inf and nan)
    assert len(caplog.records) == 2
    assert "test_context.invalid_float_filtered" in caplog.text


def test_filter_valid_floats_logging_disabled(caplog):
    """Test that filter_valid_floats doesn't log when disabled."""
    caplog.set_level(logging.WARNING)

    values = [1.0, float("inf"), float("nan")]
    filter_valid_floats(values, log_invalid=False)

    # Should not have logged anything
    assert len(caplog.records) == 0
