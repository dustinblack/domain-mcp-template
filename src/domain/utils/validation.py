"""
Validation utilities for numeric data.

Provides utilities for validating and sanitizing float values, with special
handling for infinity, NaN, and JSON serialization requirements.
"""

import logging
import math
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


def is_valid_float(value: float) -> bool:
    """
    Check if a float value is finite and JSON-serializable.

    Parameters
    ----------
    value : float
        The float value to check

    Returns
    -------
    bool
        True if the value is finite (not inf, -inf, or nan), False otherwise

    Examples
    --------
    >>> is_valid_float(42.5)
    True
    >>> is_valid_float(float('inf'))
    False
    >>> is_valid_float(float('nan'))
    False
    """
    return math.isfinite(value)


def sanitize_float(
    value: float,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    Sanitize a float value with validation and range checking.

    Parameters
    ----------
    value : float
        The float value to sanitize
    min_value : float, optional
        Minimum acceptable value (inclusive)
    max_value : float, optional
        Maximum acceptable value (inclusive)
    default : float, optional
        Default value to return if validation fails. If None, returns None.

    Returns
    -------
    float or None
        Sanitized value if valid, default value otherwise

    Examples
    --------
    >>> sanitize_float(42.5)
    42.5
    >>> sanitize_float(float('inf'))
    None
    >>> sanitize_float(float('inf'), default=0.0)
    0.0
    >>> sanitize_float(150.0, max_value=100.0, default=100.0)
    100.0
    >>> sanitize_float(-5.0, min_value=0.0, default=0.0)
    0.0
    """
    # Check if finite
    if not is_valid_float(value):
        return default

    # Check range
    if min_value is not None and value < min_value:
        return default
    if max_value is not None and value > max_value:
        return default

    return value


def filter_valid_floats(
    values: List[float],
    log_invalid: bool = True,
    log_context: str = "unknown",
) -> Tuple[List[float], int]:
    """
    Filter a list of floats to only include valid (finite) values.

    Parameters
    ----------
    values : List[float]
        List of float values to filter
    log_invalid : bool, default=True
        Whether to log warnings for invalid values
    log_context : str, default="unknown"
        Context string for logging (e.g., "boot_time.phase_values")

    Returns
    -------
    tuple of (List[float], int)
        Tuple of (valid values, count of invalid values removed)

    Examples
    --------
    >>> filter_valid_floats([1.0, 2.0, float('inf'), 3.0, float('nan')])
    ([1.0, 2.0, 3.0], 2)
    >>> filter_valid_floats([1.0, 2.0, 3.0])
    ([1.0, 2.0, 3.0], 0)
    """
    valid_values: List[float] = []
    invalid_count = 0

    for value in values:
        if is_valid_float(value):
            valid_values.append(value)
        else:
            invalid_count += 1
            if log_invalid:
                logger.warning(
                    "%s.invalid_float_filtered",
                    log_context,
                    extra={"value": str(value), "type": type(value).__name__},
                )

    return valid_values, invalid_count
