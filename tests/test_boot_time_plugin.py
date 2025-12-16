"""Unit tests for BootTimePlugin extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import src.domain.plugins.boot_time  # noqa: F401 - ensure plugin registration
from src.domain.plugins import get as get_plugin

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "boot-time"


@pytest.mark.asyncio
async def test_extract_local_successful_boot() -> None:
    """Ensure RHIVOS local fixture extracts total boot time, phases, and dimensions."""
    plugin = get_plugin("boot-time-verbose")
    data = json.loads((FIXTURES_DIR / "successful-boot.json").read_text())

    points = await plugin.extract(data, refs={})

    # Should extract total + 3 phases (kernel, initrd, system_init)
    assert len(points) == 4

    # Find and verify total boot time
    total_point = next(p for p in points if p.metric_id == "boot.time.total_ms")
    assert total_point.value == pytest.approx(12500.0)
    assert total_point.unit == "ms"
    assert total_point.dimensions is not None
    assert total_point.dimensions.get("os_id") == "rhel-9.2"
    assert total_point.dimensions.get("mode") == "standard"

    # Verify phases are extracted
    kernel_point = next(p for p in points if p.metric_id == "boot.phase.kernel_ms")
    assert kernel_point.value == pytest.approx(3000.0)

    initrd_point = next(p for p in points if p.metric_id == "boot.phase.initrd_ms")
    assert initrd_point.value == pytest.approx(1500.0)

    system_init_point = next(
        p for p in points if p.metric_id == "boot.phase.system_init_ms"
    )
    assert system_init_point.value == pytest.approx(5500.0)


@pytest.mark.asyncio
async def test_extract_horreum_v4_sample() -> None:
    """Ensure Horreum v4 sample extracts total, phases, timestamps, and dimensions."""
    plugin = get_plugin("boot-time-verbose")
    data = json.loads((FIXTURES_DIR / "horreum-v4-sample.json").read_text())

    points = await plugin.extract(data, refs={})

    # Should extract: total + 4 phases + 4 timestamps = 9 metrics
    # Phases: kernel_pre_timer, kernel, initrd, system_init (switchroot not in fixture)
    # Timestamps: early_service, start_kmod_load, first_service, network_online
    assert len(points) == 9

    # Find and verify total boot time
    total_point = next(p for p in points if p.metric_id == "boot.time.total_ms")
    assert total_point.value == pytest.approx(18000.0)
    assert total_point.unit == "ms"
    assert total_point.dimensions is not None
    assert total_point.dimensions.get("os_id") == "rhel"
    # In v4 datasets, image_target can be systemd target OR hardware platform
    # Here it's "multi-user" (systemd target), stored in 'target' dimension
    assert total_point.dimensions.get("target") == "multi-user"

    # Verify all 4 phases present in fixture
    kernel_pre_timer = next(
        p for p in points if p.metric_id == "boot.phase.kernel_pre_timer_ms"
    )
    assert kernel_pre_timer.value == pytest.approx(500.0)

    kernel_point = next(p for p in points if p.metric_id == "boot.phase.kernel_ms")
    assert kernel_point.value == pytest.approx(4200.0)

    initrd_point = next(p for p in points if p.metric_id == "boot.phase.initrd_ms")
    assert initrd_point.value == pytest.approx(2800.0)

    system_init_point = next(
        p for p in points if p.metric_id == "boot.phase.system_init_ms"
    )
    assert system_init_point.value == pytest.approx(11000.0)

    # Verify all 4 critical timestamps
    early_service_point = next(
        p for p in points if p.metric_id == "boot.timestamp.early_service_ms"
    )
    assert early_service_point.value == pytest.approx(6500.0)

    start_kmod_point = next(
        p for p in points if p.metric_id == "boot.timestamp.start_kmod_load_ms"
    )
    assert start_kmod_point.value == pytest.approx(6000.0)

    first_service_point = next(
        p for p in points if p.metric_id == "boot.timestamp.first_service_ms"
    )
    assert first_service_point.value == pytest.approx(12000.0)

    network_online_point = next(
        p for p in points if p.metric_id == "boot.timestamp.network_online_ms"
    )
    assert network_online_point.value == pytest.approx(12000.0)
