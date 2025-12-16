"""Command-line interface to start the Domain MCP server.

This CLI loads application configuration, initializes source adapters, and
starts the server lifecycle in the foreground. It is intended for development
and basic deployments while the HTTP/MCP transports are being designed.

Usage
-----
    python -m src.server.cli --config config.json
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from ..adapters import log_adapter_status, register_adapter
from ..adapters.horreum import HorreumAdapter
from ..adapters.mcp_bridge import MCPBridgeAdapter
from ..config.models import AppConfig
from ..observability import setup_logging
from .app import DomainMCPServer
from .http import create_app


async def _init_from_config(config_path: Path) -> DomainMCPServer:
    """Initialize adapters and server from a JSON config file.

    Parameters
    ----------
    config_path: Path
        Filesystem path to the JSON configuration file.

    Returns
    -------
    DomainMCPServer
        A server instance ready to start.
    """
    cfg = AppConfig.load(config_path)
    for source_id, sc in cfg.sources.items():
        if sc.type in ("horreum", "horreum-mcp-http", "http"):
            register_adapter(
                source_id,
                HorreumAdapter(
                    sc.endpoint,
                    sc.api_key,
                    sc.timeout_seconds,
                    max_retries=sc.max_retries,
                    backoff_initial_ms=sc.backoff_initial_ms,
                    backoff_multiplier=sc.backoff_multiplier,
                ),
            )
        elif sc.type in ("horreum-stdio", "horreum-mcp-stdio", "stdio"):
            register_adapter(
                source_id,
                MCPBridgeAdapter(
                    command=sc.endpoint,
                    args=sc.stdio_args or [],
                    timeout=sc.timeout_seconds,
                    env=sc.env or {},
                ),
            )
    log_adapter_status()
    return DomainMCPServer()


async def _run(config_path: Path) -> None:
    """Start server after applying configuration; block until interrupted.

    Sets up logging, builds the server, and keeps the process alive until an
    interrupt signal is received.
    """
    setup_logging()
    server = await _init_from_config(config_path)
    await server.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await server.stop()


def main() -> None:
    """CLI entrypoint for running the Domain MCP server.

    Provides two modes:
    - stdio/foreground server loop (default) using --config
    - HTTP mode with FastAPI when --http is specified
    """
    parser = argparse.ArgumentParser(description="Domain MCP CLI")
    parser.add_argument("--config", help="Path to JSON app config")
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=[
            "CRITICAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
        ],
        help="Logging level (overrides environment)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (once sets DEBUG)",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Run HTTP server (requires fastapi/uvicorn)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="HTTP bind host (default 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8080, help="HTTP port")
    args = parser.parse_args()

    # Determine effective log level
    env_level = os.environ.get("DOMAIN_MCP_LOG_LEVEL", "INFO").upper()
    effective_level = args.log_level or ("DEBUG" if args.verbose > 0 else env_level)
    # Apply early so subsequent imports use configured level
    setup_logging(effective_level)

    if args.http:
        # Lazy import uvicorn only for HTTP mode
        import importlib

        uvicorn = importlib.import_module("uvicorn")
        app = create_app()
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,  # type: ignore[attr-defined]
            log_level=effective_level.lower(),
        )
        return

    if not args.config:
        parser.error("--config is required unless --http is used")
    asyncio.run(_run(Path(args.config)))


if __name__ == "__main__":
    main()
