"""Test plugin registration and logging functionality."""

from __future__ import annotations

import logging

from src.domain.plugins import get, log_plugin_status


def test_plugin_registration_includes_boot_time():
    """Ensure boot-time-verbose plugin is registered automatically."""
    plugin = get("boot-time-verbose")
    assert plugin.id == "boot-time-verbose"
    assert len(plugin.kpis) > 0


def test_log_plugin_status_output(caplog):
    """Test that log_plugin_status produces expected log messages."""
    with caplog.at_level(logging.INFO):
        log_plugin_status()

    # Should have at least one INFO log about plugins loaded
    info_logs = [
        record.message for record in caplog.records if record.levelname == "INFO"
    ]
    assert len(info_logs) > 0

    # Should mention boot-time-verbose plugin
    combined_logs = " ".join(info_logs)
    assert "boot-time-verbose" in combined_logs
    assert "Available dataset types" in combined_logs


def test_plugin_import_no_circular_dependency():
    """Ensure plugin imports don't cause circular dependency errors."""
    # This test passes if the import succeeds without ImportError
    from src.domain.plugins import boot_time  # noqa: F401, E402

    # Should be able to access the plugin after import
    plugin = get("boot-time-verbose")
    assert plugin.id == "boot-time-verbose"
