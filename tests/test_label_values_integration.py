from __future__ import annotations

from typing import Any, Dict, List

import pytest

from src.domain.plugins import get as get_plugin


@pytest.mark.asyncio
async def test_boot_time_extract_from_label_values_simple():
    """Test total boot time is calculated from boot phases, not extracted."""
    plugin = get_plugin("boot-time-verbose")
    items: List[Dict[str, Any]] = [
        {
            "values": [
                # Boot phases are used to calculate total
                {"name": "BOOT0 - SystemInit Duration Average ms", "value": 5000},
                {
                    "name": "BOOT2 - Kernel Post-Timer Duration Average ms",
                    "value": 3000,
                },
                {"name": "BOOT3 - Initrd Duration Average ms", "value": 2000},
                {"name": "BOOT4 - Switchroot Duration Average ms", "value": 1000},
                # BOOT1 (kernel_pre_timer) is missing - should be treated as 0
                {"name": "unrelated", "value": 1},
            ],
            "start": "2025-10-07T10:00:00Z",
            "stop": "2025-10-07T10:01:00Z",
        }
    ]
    points = await plugin.extract_from_label_values(items)  # type: ignore[attr-defined]

    # Should return 4 phases + 1 calculated total = 5 metrics
    assert len(points) == 5, f"Expected 5 metrics, got {len(points)}"

    # Find the total metric
    total = next((p for p in points if p.metric_id == "boot.time.total_ms"), None)
    assert total is not None, "Should have calculated total boot time"

    # Total should be sum of phases (5000 + 3000 + 2000 + 1000 = 11000)
    # Note: BOOT1 (kernel_pre_timer) is not in the input, so it's not included
    # Only non-numeric values (like "Need to collect") trigger missing_phases tracking
    assert total.value == 11000.0, f"Expected 11000.0, got {total.value}"
    assert total.unit == "ms"

    # Should have statistic_type dimension
    assert total.dimensions is not None, "Total should have dimensions"
    assert total.dimensions["statistic_type"] == "average"
