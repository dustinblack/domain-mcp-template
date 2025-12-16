"""Server CLI lifecycle smoke test.

Starts and stops the server run loop quickly to ensure no unhandled exceptions
occur during startup/shutdown. Uses a minimal config file with a dummy source.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.server.cli import _init_from_config


@pytest.mark.asyncio
async def test_cli_init_from_config_tmp(tmp_path: Path) -> None:
    """Start and stop server using a minimal temporary JSON config."""
    cfg = {
        "sources": {
            "horreum-dev": {
                "endpoint": "http://localhost:3001",
                "api_key": "",
                "type": "horreum",
                "timeout_seconds": 5,
            }
        },
        "enabled_plugins": {"boot-time-verbose": True},
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))

    server = await _init_from_config(cfg_path)
    # Ensure we can start and stop without exceptions
    await server.start()
    await server.stop()
