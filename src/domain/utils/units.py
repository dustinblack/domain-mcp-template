"""
Unit conversion utilities for time and data measurements.

Provides utilities for converting between different time units (milliseconds,
seconds, minutes, hours) and data units (bytes, kilobytes, megabytes, gigabytes).
Includes auto-scaling functions for human-readable display.
"""

import logging
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class TimeUnit(Enum):
    """Time units for conversion."""

    MILLISECONDS = "ms"
    SECONDS = "s"
    MINUTES = "min"
    HOURS = "h"
    DAYS = "d"


class DataUnit(Enum):
    """Data units for conversion."""

    BYTES = "B"
    KILOBYTES = "KB"
    MEGABYTES = "MB"
    GIGABYTES = "GB"
    TERABYTES = "TB"


# Time conversion factors to milliseconds
_TIME_TO_MS = {
    TimeUnit.MILLISECONDS: 1.0,
    TimeUnit.SECONDS: 1000.0,
    TimeUnit.MINUTES: 60_000.0,
    TimeUnit.HOURS: 3_600_000.0,
    TimeUnit.DAYS: 86_400_000.0,
}

# Data conversion factors to bytes
_DATA_TO_BYTES = {
    DataUnit.BYTES: 1.0,
    DataUnit.KILOBYTES: 1024.0,
    DataUnit.MEGABYTES: 1024.0**2,
    DataUnit.GIGABYTES: 1024.0**3,
    DataUnit.TERABYTES: 1024.0**4,
}


def convert_time(
    value: float, from_unit: TimeUnit, to_unit: TimeUnit
) -> Optional[float]:
    """
    Convert time value between different units.

    Parameters
    ----------
    value : float
        The time value to convert
    from_unit : TimeUnit
        The source unit
    to_unit : TimeUnit
        The target unit

    Returns
    -------
    float or None
        Converted value, or None if conversion fails

    Examples
    --------
    >>> convert_time(1000.0, TimeUnit.MILLISECONDS, TimeUnit.SECONDS)
    1.0
    >>> convert_time(2.5, TimeUnit.MINUTES, TimeUnit.SECONDS)
    150.0
    >>> convert_time(1.0, TimeUnit.HOURS, TimeUnit.MINUTES)
    60.0
    """
    if value < 0:
        logger.warning(
            "units.convert_time.negative_value",
            extra={"value": value, "from_unit": from_unit.value},
        )
        return None

    try:
        # Convert to milliseconds first
        ms_value = value * _TIME_TO_MS[from_unit]
        # Convert from milliseconds to target unit
        result = ms_value / _TIME_TO_MS[to_unit]
        return result
    except (ValueError, KeyError, ZeroDivisionError) as e:
        logger.warning(
            "units.convert_time.failed",
            extra={
                "error": str(e),
                "value": value,
                "from_unit": from_unit.value,
                "to_unit": to_unit.value,
            },
        )
        return None


def convert_data(
    value: float, from_unit: DataUnit, to_unit: DataUnit
) -> Optional[float]:
    """
    Convert data value between different units.

    Parameters
    ----------
    value : float
        The data value to convert
    from_unit : DataUnit
        The source unit
    to_unit : DataUnit
        The target unit

    Returns
    -------
    float or None
        Converted value, or None if conversion fails

    Examples
    --------
    >>> convert_data(1024.0, DataUnit.BYTES, DataUnit.KILOBYTES)
    1.0
    >>> convert_data(1.5, DataUnit.MEGABYTES, DataUnit.KILOBYTES)
    1536.0
    >>> convert_data(1.0, DataUnit.GIGABYTES, DataUnit.MEGABYTES)
    1024.0
    """
    if value < 0:
        logger.warning(
            "units.convert_data.negative_value",
            extra={"value": value, "from_unit": from_unit.value},
        )
        return None

    try:
        # Convert to bytes first
        bytes_value = value * _DATA_TO_BYTES[from_unit]
        # Convert from bytes to target unit
        result = bytes_value / _DATA_TO_BYTES[to_unit]
        return result
    except (ValueError, KeyError, ZeroDivisionError) as e:
        logger.warning(
            "units.convert_data.failed",
            extra={
                "error": str(e),
                "value": value,
                "from_unit": from_unit.value,
                "to_unit": to_unit.value,
            },
        )
        return None


def auto_scale_time(value_ms: float, precision: int = 2) -> Tuple[float, str]:
    """
    Automatically scale time to most appropriate unit for display.

    Parameters
    ----------
    value_ms : float
        Time value in milliseconds
    precision : int, default=2
        Number of decimal places for rounding

    Returns
    -------
    tuple of (float, str)
        (scaled_value, unit_string) for display

    Examples
    --------
    >>> auto_scale_time(500.0)
    (500.0, 'ms')
    >>> auto_scale_time(5000.0)
    (5.0, 's')
    >>> auto_scale_time(125000.0)
    (2.08, 'min')
    >>> auto_scale_time(7200000.0)
    (2.0, 'h')
    """
    if value_ms < 0:
        return (value_ms, "ms")

    # Thresholds for auto-scaling
    if value_ms < 1000.0:  # < 1 second
        return (round(value_ms, precision), "ms")
    if value_ms < 60_000.0:  # < 1 minute
        return (round(value_ms / 1000.0, precision), "s")
    if value_ms < 3_600_000.0:  # < 1 hour
        return (round(value_ms / 60_000.0, precision), "min")
    if value_ms < 86_400_000.0:  # < 1 day
        return (round(value_ms / 3_600_000.0, precision), "h")
    # >= 1 day
    return (round(value_ms / 86_400_000.0, precision), "d")


def auto_scale_data(value_bytes: float, precision: int = 2) -> Tuple[float, str]:
    """
    Automatically scale data to most appropriate unit for display.

    Parameters
    ----------
    value_bytes : float
        Data value in bytes
    precision : int, default=2
        Number of decimal places for rounding

    Returns
    -------
    tuple of (float, str)
        (scaled_value, unit_string) for display

    Examples
    --------
    >>> auto_scale_data(500.0)
    (500.0, 'B')
    >>> auto_scale_data(5120.0)
    (5.0, 'KB')
    >>> auto_scale_data(1572864.0)
    (1.5, 'MB')
    >>> auto_scale_data(1073741824.0)
    (1.0, 'GB')
    """
    if value_bytes < 0:
        return (value_bytes, "B")

    # Thresholds for auto-scaling (using binary units: 1024)
    if value_bytes < 1024.0:  # < 1 KB
        return (round(value_bytes, precision), "B")
    if value_bytes < 1024.0**2:  # < 1 MB
        return (round(value_bytes / 1024.0, precision), "KB")
    if value_bytes < 1024.0**3:  # < 1 GB
        return (round(value_bytes / (1024.0**2), precision), "MB")
    if value_bytes < 1024.0**4:  # < 1 TB
        return (round(value_bytes / (1024.0**3), precision), "GB")
    # >= 1 TB
    return (round(value_bytes / (1024.0**4), precision), "TB")
