"""
Tests for unit conversion utilities.
"""

from src.domain.utils.units import (
    DataUnit,
    TimeUnit,
    auto_scale_data,
    auto_scale_time,
    convert_data,
    convert_time,
)

# ============================================================================
# TimeUnit conversion tests
# ============================================================================


def test_convert_time_ms_to_s():
    """Test milliseconds to seconds conversion."""
    result = convert_time(1000.0, TimeUnit.MILLISECONDS, TimeUnit.SECONDS)
    assert result == 1.0


def test_convert_time_s_to_ms():
    """Test seconds to milliseconds conversion."""
    result = convert_time(1.0, TimeUnit.SECONDS, TimeUnit.MILLISECONDS)
    assert result == 1000.0


def test_convert_time_min_to_s():
    """Test minutes to seconds conversion."""
    result = convert_time(2.5, TimeUnit.MINUTES, TimeUnit.SECONDS)
    assert result == 150.0


def test_convert_time_s_to_min():
    """Test seconds to minutes conversion."""
    result = convert_time(150.0, TimeUnit.SECONDS, TimeUnit.MINUTES)
    assert result == 2.5


def test_convert_time_h_to_min():
    """Test hours to minutes conversion."""
    result = convert_time(1.5, TimeUnit.HOURS, TimeUnit.MINUTES)
    assert result == 90.0


def test_convert_time_min_to_h():
    """Test minutes to hours conversion."""
    result = convert_time(90.0, TimeUnit.MINUTES, TimeUnit.HOURS)
    assert result == 1.5


def test_convert_time_h_to_ms():
    """Test hours to milliseconds conversion."""
    result = convert_time(1.0, TimeUnit.HOURS, TimeUnit.MILLISECONDS)
    assert result == 3_600_000.0


def test_convert_time_ms_to_h():
    """Test milliseconds to hours conversion."""
    result = convert_time(3_600_000.0, TimeUnit.MILLISECONDS, TimeUnit.HOURS)
    assert result == 1.0


def test_convert_time_d_to_h():
    """Test days to hours conversion."""
    result = convert_time(1.0, TimeUnit.DAYS, TimeUnit.HOURS)
    assert result == 24.0


def test_convert_time_h_to_d():
    """Test hours to days conversion."""
    result = convert_time(24.0, TimeUnit.HOURS, TimeUnit.DAYS)
    assert result == 1.0


def test_convert_time_same_unit():
    """Test conversion when source and target units are same."""
    result = convert_time(42.0, TimeUnit.SECONDS, TimeUnit.SECONDS)
    assert result == 42.0


def test_convert_time_zero():
    """Test conversion of zero value."""
    result = convert_time(0.0, TimeUnit.MILLISECONDS, TimeUnit.SECONDS)
    assert result == 0.0


def test_convert_time_negative():
    """Test conversion with negative value (should return None)."""
    result = convert_time(-100.0, TimeUnit.SECONDS, TimeUnit.MILLISECONDS)
    assert result is None


def test_convert_time_fractional():
    """Test conversion with fractional values."""
    result = convert_time(1.5, TimeUnit.SECONDS, TimeUnit.MILLISECONDS)
    assert result == 1500.0


# ============================================================================
# DataUnit conversion tests
# ============================================================================


def test_convert_data_b_to_kb():
    """Test bytes to kilobytes conversion."""
    result = convert_data(1024.0, DataUnit.BYTES, DataUnit.KILOBYTES)
    assert result == 1.0


def test_convert_data_kb_to_b():
    """Test kilobytes to bytes conversion."""
    result = convert_data(1.0, DataUnit.KILOBYTES, DataUnit.BYTES)
    assert result == 1024.0


def test_convert_data_mb_to_kb():
    """Test megabytes to kilobytes conversion."""
    result = convert_data(1.5, DataUnit.MEGABYTES, DataUnit.KILOBYTES)
    assert result == 1536.0


def test_convert_data_kb_to_mb():
    """Test kilobytes to megabytes conversion."""
    result = convert_data(1536.0, DataUnit.KILOBYTES, DataUnit.MEGABYTES)
    assert result == 1.5


def test_convert_data_gb_to_mb():
    """Test gigabytes to megabytes conversion."""
    result = convert_data(1.0, DataUnit.GIGABYTES, DataUnit.MEGABYTES)
    assert result == 1024.0


def test_convert_data_mb_to_gb():
    """Test megabytes to gigabytes conversion."""
    result = convert_data(1024.0, DataUnit.MEGABYTES, DataUnit.GIGABYTES)
    assert result == 1.0


def test_convert_data_gb_to_b():
    """Test gigabytes to bytes conversion."""
    result = convert_data(1.0, DataUnit.GIGABYTES, DataUnit.BYTES)
    assert result == 1024.0**3


def test_convert_data_b_to_gb():
    """Test bytes to gigabytes conversion."""
    result = convert_data(1024.0**3, DataUnit.BYTES, DataUnit.GIGABYTES)
    assert result == 1.0


def test_convert_data_tb_to_gb():
    """Test terabytes to gigabytes conversion."""
    result = convert_data(1.0, DataUnit.TERABYTES, DataUnit.GIGABYTES)
    assert result == 1024.0


def test_convert_data_gb_to_tb():
    """Test gigabytes to terabytes conversion."""
    result = convert_data(1024.0, DataUnit.GIGABYTES, DataUnit.TERABYTES)
    assert result == 1.0


def test_convert_data_same_unit():
    """Test conversion when source and target units are same."""
    result = convert_data(42.0, DataUnit.MEGABYTES, DataUnit.MEGABYTES)
    assert result == 42.0


def test_convert_data_zero():
    """Test conversion of zero value."""
    result = convert_data(0.0, DataUnit.BYTES, DataUnit.KILOBYTES)
    assert result == 0.0


def test_convert_data_negative():
    """Test conversion with negative value (should return None)."""
    result = convert_data(-100.0, DataUnit.BYTES, DataUnit.KILOBYTES)
    assert result is None


def test_convert_data_fractional():
    """Test conversion with fractional values."""
    result = convert_data(1.5, DataUnit.KILOBYTES, DataUnit.BYTES)
    assert result == 1536.0


# ============================================================================
# auto_scale_time tests
# ============================================================================


def test_auto_scale_time_milliseconds():
    """Test auto-scaling for small values (< 1 second)."""
    value, unit = auto_scale_time(500.0)
    assert value == 500.0
    assert unit == "ms"


def test_auto_scale_time_seconds():
    """Test auto-scaling for seconds range."""
    value, unit = auto_scale_time(5000.0)
    assert value == 5.0
    assert unit == "s"


def test_auto_scale_time_minutes():
    """Test auto-scaling for minutes range."""
    value, unit = auto_scale_time(125000.0)  # 2.08 minutes
    assert 2.08 <= value <= 2.09
    assert unit == "min"


def test_auto_scale_time_hours():
    """Test auto-scaling for hours range."""
    value, unit = auto_scale_time(7200000.0)  # 2 hours
    assert value == 2.0
    assert unit == "h"


def test_auto_scale_time_days():
    """Test auto-scaling for days range."""
    value, unit = auto_scale_time(172800000.0)  # 2 days
    assert value == 2.0
    assert unit == "d"


def test_auto_scale_time_zero():
    """Test auto-scaling for zero value."""
    value, unit = auto_scale_time(0.0)
    assert value == 0.0
    assert unit == "ms"


def test_auto_scale_time_negative():
    """Test auto-scaling with negative value (returns as-is with ms)."""
    value, unit = auto_scale_time(-100.0)
    assert value == -100.0
    assert unit == "ms"


def test_auto_scale_time_precision():
    """Test precision parameter for auto-scaling."""
    value, unit = auto_scale_time(1234.5678, precision=1)
    assert value == 1.2
    assert unit == "s"


def test_auto_scale_time_threshold_boundaries():
    """Test auto-scaling at unit threshold boundaries."""
    # Just under 1 second
    _, unit = auto_scale_time(999.0)
    assert unit == "ms"

    # Just at 1 second
    _, unit = auto_scale_time(1000.0)
    assert unit == "s"

    # Just under 1 minute
    _, unit = auto_scale_time(59999.0)
    assert unit == "s"

    # Just at 1 minute
    _, unit = auto_scale_time(60000.0)
    assert unit == "min"


# ============================================================================
# auto_scale_data tests
# ============================================================================


def test_auto_scale_data_bytes():
    """Test auto-scaling for small values (< 1 KB)."""
    value, unit = auto_scale_data(500.0)
    assert value == 500.0
    assert unit == "B"


def test_auto_scale_data_kilobytes():
    """Test auto-scaling for kilobytes range."""
    value, unit = auto_scale_data(5120.0)
    assert value == 5.0
    assert unit == "KB"


def test_auto_scale_data_megabytes():
    """Test auto-scaling for megabytes range."""
    value, unit = auto_scale_data(1572864.0)  # 1.5 MB
    assert value == 1.5
    assert unit == "MB"


def test_auto_scale_data_gigabytes():
    """Test auto-scaling for gigabytes range."""
    value, unit = auto_scale_data(2147483648.0)  # 2 GB
    assert value == 2.0
    assert unit == "GB"


def test_auto_scale_data_terabytes():
    """Test auto-scaling for terabytes range."""
    value, unit = auto_scale_data(2199023255552.0)  # 2 TB
    assert value == 2.0
    assert unit == "TB"


def test_auto_scale_data_zero():
    """Test auto-scaling for zero value."""
    value, unit = auto_scale_data(0.0)
    assert value == 0.0
    assert unit == "B"


def test_auto_scale_data_negative():
    """Test auto-scaling with negative value (returns as-is with B)."""
    value, unit = auto_scale_data(-100.0)
    assert value == -100.0
    assert unit == "B"


def test_auto_scale_data_precision():
    """Test precision parameter for auto-scaling."""
    value, unit = auto_scale_data(1234567.0, precision=1)
    assert value == 1.2
    assert unit == "MB"


def test_auto_scale_data_threshold_boundaries():
    """Test auto-scaling at unit threshold boundaries."""
    # Just under 1 KB
    _, unit = auto_scale_data(1023.0)
    assert unit == "B"

    # Just at 1 KB
    _, unit = auto_scale_data(1024.0)
    assert unit == "KB"

    # Just under 1 MB
    _, unit = auto_scale_data(1024.0**2 - 1)
    assert unit == "KB"

    # Just at 1 MB
    _, unit = auto_scale_data(1024.0**2)
    assert unit == "MB"


# ============================================================================
# Edge cases and integration tests
# ============================================================================


def test_time_conversion_roundtrip():
    """Test roundtrip conversion maintains value."""
    original = 1234.5
    converted = convert_time(original, TimeUnit.SECONDS, TimeUnit.MILLISECONDS)
    back = convert_time(converted, TimeUnit.MILLISECONDS, TimeUnit.SECONDS)
    assert abs(back - original) < 0.001


def test_data_conversion_roundtrip():
    """Test roundtrip conversion maintains value."""
    original = 5678.9
    converted = convert_data(original, DataUnit.MEGABYTES, DataUnit.BYTES)
    back = convert_data(converted, DataUnit.BYTES, DataUnit.MEGABYTES)
    assert abs(back - original) < 0.001


def test_time_conversion_chain():
    """Test chaining multiple conversions."""
    # Start with 1 hour
    result = convert_time(1.0, TimeUnit.HOURS, TimeUnit.MINUTES)
    assert result == 60.0
    result = convert_time(result, TimeUnit.MINUTES, TimeUnit.SECONDS)
    assert result == 3600.0
    result = convert_time(result, TimeUnit.SECONDS, TimeUnit.MILLISECONDS)
    assert result == 3_600_000.0


def test_data_conversion_chain():
    """Test chaining multiple conversions."""
    # Start with 1 GB
    result = convert_data(1.0, DataUnit.GIGABYTES, DataUnit.MEGABYTES)
    assert result == 1024.0
    result = convert_data(result, DataUnit.MEGABYTES, DataUnit.KILOBYTES)
    assert result == 1024.0**2
    result = convert_data(result, DataUnit.KILOBYTES, DataUnit.BYTES)
    assert result == 1024.0**3


def test_auto_scale_time_and_convert():
    """Test using auto-scale and manual conversion together."""
    # Start with a large millisecond value
    ms_value = 125000.0
    scaled_value, scaled_unit = auto_scale_time(ms_value)

    # Should scale to minutes
    assert scaled_unit == "min"
    assert 2.08 <= scaled_value <= 2.09

    # Verify by converting back
    if scaled_unit == "min":
        back_to_ms = convert_time(scaled_value, TimeUnit.MINUTES, TimeUnit.MILLISECONDS)
        # Allow rounding error from 2 decimal places: 2.08 * 60000 = 124800
        assert abs(back_to_ms - ms_value) < 1000.0


def test_auto_scale_data_and_convert():
    """Test using auto-scale and manual conversion together."""
    # Start with a large byte value
    bytes_value = 1572864.0  # 1.5 MB
    scaled_value, scaled_unit = auto_scale_data(bytes_value)

    # Should scale to megabytes
    assert scaled_unit == "MB"
    assert scaled_value == 1.5

    # Verify by converting back
    if scaled_unit == "MB":
        back_to_bytes = convert_data(scaled_value, DataUnit.MEGABYTES, DataUnit.BYTES)
        assert abs(back_to_bytes - bytes_value) < 1.0  # Allow small rounding error
