"""Test adapter registration and logging functionality."""

from __future__ import annotations

import logging

from src.adapters import _adapters as adapter_registry
from src.adapters import log_adapter_status, register_adapter
from src.adapters.horreum import HorreumAdapter


def test_log_adapter_status_no_adapters(caplog):
    """Test log_adapter_status when no adapters are configured."""
    # Clear any existing adapters
    adapter_registry.clear()

    with caplog.at_level(logging.WARNING):
        log_adapter_status()

    # Should have warning about no external MCP servers
    warning_logs = [
        record.message for record in caplog.records if record.levelname == "WARNING"
    ]
    assert len(warning_logs) > 0

    combined_logs = " ".join(warning_logs)
    assert "No external MCP servers configured" in combined_logs
    assert "Only raw mode functionality available" in combined_logs


def test_log_adapter_status_with_adapters(caplog):
    """Test log_adapter_status when adapters are configured."""
    # Register a test adapter
    adapter = HorreumAdapter("http://test-horreum-mcp:8080", timeout=30)
    register_adapter("test-source", adapter)

    try:
        with caplog.at_level(logging.INFO):
            log_adapter_status()

        # Should have info log about configured adapters
        info_logs = [
            record.message for record in caplog.records if record.levelname == "INFO"
        ]
        assert len(info_logs) > 0

        combined_logs = " ".join(info_logs)
        assert "External MCP server connections configured" in combined_logs
        assert "test-source" in combined_logs

    finally:
        # Clean up
        adapter_registry.clear()


def test_adapter_registry_clear():
    """Test that adapter registry can be cleared for testing."""
    # Register a test adapter
    adapter = HorreumAdapter("http://example", timeout=30)
    register_adapter("test", adapter)

    assert "test" in adapter_registry

    # Clear and verify
    adapter_registry.clear()
    assert len(adapter_registry) == 0
