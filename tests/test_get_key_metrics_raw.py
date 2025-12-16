"""Tests for get_key_metrics raw mode handler."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from src.server.app import DomainMCPServer

# Ensure Boot-Time plugin is registered via import side-effect
importlib.import_module("src.domain.examples.horreum_boot_time")


@pytest.mark.asyncio
async def test_get_key_metrics_raw_boot_time_fixture() -> None:
    """Ensure raw-mode handler extracts boot-time metrics from fixtures."""
    server = DomainMCPServer()
    await server.start()

    fixture_dir = Path(__file__).parent / "fixtures" / "boot-time"
    data = [
        json.loads((fixture_dir / "successful-boot.json").read_text()),
        json.loads((fixture_dir / "horreum-v4-sample.json").read_text()),
    ]

    points = await server.get_key_metrics_raw(["boot-time-verbose"], data)
    await server.stop()

    assert len(points) >= 2
    ids = {p.metric_id for p in points}
    assert "boot.time.total_ms" in ids
