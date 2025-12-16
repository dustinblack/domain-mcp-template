"""
Tests for timestamp utilities.
"""

from datetime import datetime, timezone

from src.domain.utils.timestamps import (
    calculate_time_delta_ms,
    parse_timestamp,
    to_iso8601,
    to_unix_timestamp,
)


def test_parse_timestamp_iso8601_with_z():
    """Test parsing ISO8601 timestamp with Z suffix."""
    result = parse_timestamp("2025-10-15T12:00:00Z")
    assert result is not None
    assert result.year == 2025
    assert result.month == 10
    assert result.day == 15
    assert result.hour == 12
    assert result.minute == 0
    assert result.second == 0
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_iso8601_with_timezone():
    """Test parsing ISO8601 timestamp with +00:00 timezone."""
    result = parse_timestamp("2025-10-15T12:00:00+00:00")
    assert result is not None
    assert result.year == 2025
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_iso8601_without_timezone():
    """Test parsing ISO8601 timestamp without timezone (defaults to UTC)."""
    result = parse_timestamp("2025-10-15T12:00:00")
    assert result is not None
    assert result.year == 2025
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_unix_seconds():
    """Test parsing Unix timestamp in seconds."""
    # October 15, 2023 16:00:00 UTC
    result = parse_timestamp(1697385600)
    assert result is not None
    assert result.year == 2023
    assert result.month == 10
    assert result.day == 15
    assert result.hour == 16
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_unix_milliseconds():
    """Test parsing Unix timestamp in milliseconds."""
    # October 15, 2023 16:00:00 UTC
    result = parse_timestamp(1697385600000)
    assert result is not None
    assert result.year == 2023
    assert result.month == 10
    assert result.day == 15
    assert result.hour == 16
    assert result.tzinfo == timezone.utc


def test_parse_timestamp_unix_float_seconds():
    """Test parsing Unix timestamp as float (seconds)."""
    result = parse_timestamp(1697385600.5)
    assert result is not None
    assert result.microsecond == 500000  # 0.5 seconds = 500000 microseconds


def test_parse_timestamp_none():
    """Test parsing None returns None."""
    assert parse_timestamp(None) is None


def test_parse_timestamp_empty_string():
    """Test parsing empty string returns None."""
    assert parse_timestamp("") is None


def test_parse_timestamp_invalid_string():
    """Test parsing invalid string returns None."""
    assert parse_timestamp("invalid") is None
    assert parse_timestamp("2025-13-45T99:99:99Z") is None


def test_parse_timestamp_invalid_number():
    """Test parsing invalid number returns None."""
    # Very large number that causes OSError
    assert parse_timestamp(999999999999999) is None


def test_parse_timestamp_epoch_zero():
    """Test parsing Unix epoch zero (January 1, 1970)."""
    result = parse_timestamp(0)
    assert result is not None
    assert result.year == 1970
    assert result.month == 1
    assert result.day == 1


def test_parse_timestamp_negative_unix():
    """Test parsing negative Unix timestamp (before epoch)."""
    # December 31, 1969 23:00:00 UTC
    result = parse_timestamp(-3600)
    assert result is not None
    assert result.year == 1969
    assert result.month == 12
    assert result.day == 31


def test_calculate_time_delta_ms_simple():
    """Test calculating time delta for simple case."""
    start = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2025, 10, 15, 12, 0, 5, tzinfo=timezone.utc)
    delta = calculate_time_delta_ms(start, end)
    assert delta == 5000.0


def test_calculate_time_delta_ms_fractional():
    """Test calculating time delta with microseconds."""
    start = datetime(2025, 10, 15, 12, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2025, 10, 15, 12, 0, 0, 500000, tzinfo=timezone.utc)
    delta = calculate_time_delta_ms(start, end)
    assert delta == 500.0


def test_calculate_time_delta_ms_zero():
    """Test calculating zero time delta."""
    dt = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    delta = calculate_time_delta_ms(dt, dt)
    assert delta == 0.0


def test_calculate_time_delta_ms_negative():
    """Test calculating negative time delta."""
    start = datetime(2025, 10, 15, 12, 0, 5, tzinfo=timezone.utc)
    end = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    delta = calculate_time_delta_ms(start, end)
    assert delta == -5000.0


def test_calculate_time_delta_ms_start_none():
    """Test calculating time delta with None start."""
    end = datetime(2025, 10, 15, 12, 0, 5, tzinfo=timezone.utc)
    delta = calculate_time_delta_ms(None, end)
    assert delta is None


def test_calculate_time_delta_ms_end_none():
    """Test calculating time delta with None end."""
    start = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    delta = calculate_time_delta_ms(start, None)
    assert delta is None


def test_calculate_time_delta_ms_both_none():
    """Test calculating time delta with both None."""
    delta = calculate_time_delta_ms(None, None)
    assert delta is None


def test_to_iso8601_simple():
    """Test converting datetime to ISO8601 string."""
    dt = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = to_iso8601(dt)
    assert result == "2025-10-15T12:00:00Z"


def test_to_iso8601_with_microseconds():
    """Test converting datetime with microseconds to ISO8601."""
    dt = datetime(2025, 10, 15, 12, 0, 0, 500000, tzinfo=timezone.utc)
    result = to_iso8601(dt)
    assert result == "2025-10-15T12:00:00.500000Z"


def test_to_iso8601_none():
    """Test converting None to ISO8601 returns None."""
    assert to_iso8601(None) is None


def test_to_unix_timestamp_seconds():
    """Test converting datetime to Unix timestamp in seconds."""
    dt = datetime(2023, 10, 15, 16, 0, 0, tzinfo=timezone.utc)
    result = to_unix_timestamp(dt)
    assert result == 1697385600


def test_to_unix_timestamp_milliseconds():
    """Test converting datetime to Unix timestamp in milliseconds."""
    dt = datetime(2023, 10, 15, 16, 0, 0, tzinfo=timezone.utc)
    result = to_unix_timestamp(dt, milliseconds=True)
    assert result == 1697385600000


def test_to_unix_timestamp_epoch():
    """Test converting epoch to Unix timestamp."""
    dt = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    result = to_unix_timestamp(dt)
    assert result == 0


def test_to_unix_timestamp_none():
    """Test converting None to Unix timestamp returns None."""
    assert to_unix_timestamp(None) is None


def test_parse_and_convert_roundtrip_iso8601():
    """Test roundtrip: parse ISO8601 -> convert back to ISO8601."""
    original = "2025-10-15T12:00:00Z"
    parsed = parse_timestamp(original)
    converted = to_iso8601(parsed)
    assert converted == original


def test_parse_and_convert_roundtrip_unix():
    """Test roundtrip: parse Unix timestamp -> convert back to Unix timestamp."""
    original = 1697385600
    parsed = parse_timestamp(original)
    converted = to_unix_timestamp(parsed)
    assert converted == original


def test_parse_and_convert_roundtrip_unix_millis():
    """Test roundtrip: parse Unix millis -> convert back to Unix millis."""
    original = 1697385600000
    parsed = parse_timestamp(original)
    converted = to_unix_timestamp(parsed, milliseconds=True)
    assert converted == original


def test_unix_seconds_vs_milliseconds_threshold():
    """Test auto-detection threshold for seconds vs milliseconds."""
    # Just below threshold (treated as seconds)
    threshold_minus_1 = 9999999999
    parsed_seconds = parse_timestamp(threshold_minus_1)
    assert parsed_seconds is not None
    assert parsed_seconds.year == 2286  # Year 2286 for this timestamp in seconds

    # At threshold (treated as milliseconds)
    threshold = 10000000000
    parsed_millis = parse_timestamp(threshold)
    assert parsed_millis is not None
    assert parsed_millis.year == 1970  # Early 1970 for this timestamp in milliseconds


def test_iso8601_variations():
    """Test various ISO8601 format variations."""
    formats = [
        "2025-10-15T12:00:00Z",
        "2025-10-15T12:00:00+00:00",
        "2025-10-15T12:00:00.000Z",
        "2025-10-15T12:00:00.000000Z",
        "2025-10-15T12:00:00",
    ]

    for fmt in formats:
        result = parse_timestamp(fmt)
        assert result is not None
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 15
