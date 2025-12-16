"""
Timestamp parsing and conversion utilities.

Provides utilities for parsing ISO8601 timestamps, Unix timestamps (seconds
and milliseconds), and calculating time deltas.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Union

logger = logging.getLogger(__name__)


def parse_timestamp(value: Optional[Union[str, int, float]]) -> Optional[datetime]:
    """
    Parse a timestamp from various formats.

    Supports:
    - ISO8601 strings (with or without 'Z' suffix)
    - Unix timestamps in seconds (< 10000000000)
    - Unix timestamps in milliseconds (≥ 10000000000)

    Parameters
    ----------
    value : str, int, float, or None
        The timestamp to parse

    Returns
    -------
    datetime or None
        Parsed datetime in UTC, or None if parsing fails

    Examples
    --------
    >>> parse_timestamp("2025-10-15T12:00:00Z")
    datetime.datetime(2025, 10, 15, 12, 0, tzinfo=datetime.timezone.utc)
    >>> parse_timestamp("2025-10-15T12:00:00+00:00")
    datetime.datetime(2025, 10, 15, 12, 0, tzinfo=datetime.timezone.utc)
    >>> parse_timestamp(1697385600)  # Unix seconds
    datetime.datetime(2023, 10, 15, 12, 0, tzinfo=datetime.timezone.utc)
    >>> parse_timestamp(1697385600000)  # Unix milliseconds
    datetime.datetime(2023, 10, 15, 12, 0, tzinfo=datetime.timezone.utc)
    """
    if value is None:
        return None

    # Handle string timestamps (ISO8601)
    if isinstance(value, str):
        return _parse_iso8601(value)

    # Handle numeric timestamps (Unix seconds or milliseconds)
    if isinstance(value, (int, float)):
        return _parse_unix_timestamp(value)

    # Unsupported type
    return None


def _parse_iso8601(value: str) -> Optional[datetime]:
    """
    Parse an ISO8601 timestamp string.

    Handles trailing 'Z' by converting to '+00:00' for Python 3.11+ compatibility.
    """
    if not value:
        return None

    try:
        # Handle trailing 'Z' (Zulu time)
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        # Ensure timezone awareness (default to UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except (ValueError, TypeError):
        logger.warning(
            "timestamps.parse_iso8601_failed",
            extra={"value": value, "error": "invalid format"},
        )
        return None


def _parse_unix_timestamp(value: Union[int, float]) -> Optional[datetime]:
    """
    Parse a Unix timestamp (seconds or milliseconds since epoch).

    Auto-detects seconds vs milliseconds:
    - Values < 10000000000 are treated as seconds
    - Values ≥ 10000000000 are treated as milliseconds
    """
    try:
        # Auto-detect seconds vs milliseconds
        # Threshold: 10000000000 = September 9, 2001 in seconds
        # Any timestamp >= this is treated as milliseconds
        if value >= 10000000000:
            # Milliseconds
            return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
        else:
            # Seconds
            return datetime.fromtimestamp(value, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        logger.warning(
            "timestamps.parse_unix_failed",
            extra={"value": value, "error": "invalid timestamp"},
        )
        return None


def calculate_time_delta_ms(
    start: Optional[datetime], end: Optional[datetime]
) -> Optional[float]:
    """
    Calculate time delta in milliseconds between two timestamps.

    Parameters
    ----------
    start : datetime or None
        Start timestamp
    end : datetime or None
        End timestamp

    Returns
    -------
    float or None
        Time delta in milliseconds, or None if either timestamp is None

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> start = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    >>> end = datetime(2025, 10, 15, 12, 0, 5, tzinfo=timezone.utc)
    >>> calculate_time_delta_ms(start, end)
    5000.0
    """
    if start is None or end is None:
        return None

    try:
        delta = end - start
        return delta.total_seconds() * 1000.0
    except (ValueError, TypeError, AttributeError):
        logger.warning(
            "timestamps.calculate_delta_failed",
            extra={"start": str(start), "end": str(end)},
        )
        return None


def to_iso8601(dt: Optional[datetime]) -> Optional[str]:
    """
    Convert datetime to ISO8601 string with 'Z' suffix for UTC.

    Parameters
    ----------
    dt : datetime or None
        The datetime to convert

    Returns
    -------
    str or None
        ISO8601 string with 'Z' suffix, or None if input is None

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> dt = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    >>> to_iso8601(dt)
    '2025-10-15T12:00:00Z'
    """
    if dt is None:
        return None

    try:
        # Convert to UTC if not already
        if dt.tzinfo != timezone.utc:
            dt = dt.astimezone(timezone.utc)

        # Format and replace +00:00 with Z
        iso_str = dt.isoformat()
        if iso_str.endswith("+00:00"):
            iso_str = iso_str[:-6] + "Z"

        return iso_str
    except (ValueError, AttributeError):
        logger.warning(
            "timestamps.to_iso8601_failed",
            extra={"dt": str(dt)},
        )
        return None


def to_unix_timestamp(
    dt: Optional[datetime], milliseconds: bool = False
) -> Optional[Union[int, float]]:
    """
    Convert datetime to Unix timestamp.

    Parameters
    ----------
    dt : datetime or None
        The datetime to convert
    milliseconds : bool, default=False
        If True, return milliseconds; if False, return seconds

    Returns
    -------
    int, float, or None
        Unix timestamp, or None if input is None

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> dt = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    >>> to_unix_timestamp(dt)
    1697385600
    >>> to_unix_timestamp(dt, milliseconds=True)
    1697385600000
    """
    if dt is None:
        return None

    try:
        timestamp = dt.timestamp()
        if milliseconds:
            return int(timestamp * 1000)
        return int(timestamp)
    except (ValueError, AttributeError, OSError):
        logger.warning(
            "timestamps.to_unix_failed",
            extra={"dt": str(dt)},
        )
        return None
