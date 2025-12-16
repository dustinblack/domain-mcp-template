"""Test new adapter type support (horreum-mcp-http, horreum-mcp-stdio)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.adapters import _adapters as adapter_registry
from src.server.cli import _init_from_config


@pytest.mark.asyncio
async def test_horreum_mcp_http_adapter_type(tmp_path: Path):
    """Test that horreum-mcp-http adapter type is supported."""
    config = {
        "sources": {
            "test-horreum-mcp": {
                "type": "horreum-mcp-http",
                "endpoint": "http://test-horreum-mcp:8080",
                "api_key": "test-key",
                "timeout_seconds": 30,
            }
        }
    }

    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config))

    # Clear existing adapters
    adapter_registry.clear()

    try:
        server = await _init_from_config(config_file)
        await server.stop()

        # Verify adapter was registered
        assert "test-horreum-mcp" in adapter_registry

    finally:
        adapter_registry.clear()


@pytest.mark.asyncio
async def test_horreum_mcp_stdio_adapter_type(tmp_path: Path):
    """Test that horreum-mcp-stdio adapter type is supported."""
    config = {
        "sources": {
            "test-horreum-stdio": {
                "type": "horreum-mcp-stdio",
                "endpoint": "python",
                "stdio_args": ["-m", "horreum_mcp_server"],
                "timeout_seconds": 30,
                "env": {"HORREUM_BASE_URL": "http://horreum:8080"},
            }
        }
    }

    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config))

    # Clear existing adapters
    adapter_registry.clear()

    try:
        server = await _init_from_config(config_file)
        await server.stop()

        # Verify adapter was registered
        assert "test-horreum-stdio" in adapter_registry

    finally:
        adapter_registry.clear()


def test_config_model_default_type():
    """Test that SourceConfig defaults to horreum-mcp-http type."""
    from src.config.models import SourceConfig  # noqa: E402

    # Create minimal config
    config = SourceConfig(endpoint="http://example")
    assert config.type == "horreum-mcp-http"


@pytest.mark.asyncio
async def test_legacy_adapter_types_still_work(tmp_path: Path):
    """Test that legacy 'horreum' and 'horreum-stdio' types still work."""
    config = {
        "sources": {
            "legacy-http": {
                "type": "horreum",
                "endpoint": "http://legacy-horreum:8080",
                "api_key": "test-key",
                "timeout_seconds": 30,
            },
            "legacy-stdio": {
                "type": "horreum-stdio",
                "endpoint": "python",
                "stdio_args": ["-m", "legacy_server"],
                "timeout_seconds": 30,
            },
        }
    }

    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config))

    # Clear existing adapters
    adapter_registry.clear()

    try:
        server = await _init_from_config(config_file)
        await server.stop()

        # Verify both legacy adapters were registered
        assert "legacy-http" in adapter_registry
        assert "legacy-stdio" in adapter_registry

    finally:
        adapter_registry.clear()
