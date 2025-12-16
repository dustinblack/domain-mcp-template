"""Observability utilities: logging and tracing setup.

This module configures standard logging and, if available, integrates
`structlog` for structured logs. The dependency on `structlog` is optional to
keep the base runtime lightweight.
"""

from __future__ import annotations

import importlib
import logging


def setup_logging(level: str = "INFO") -> None:
    """Configure application logging.

    Parameters
    ----------
    level: str
        Logging level name (e.g., "DEBUG", "INFO"). Defaults to "INFO".

    Behavior
    --------
    - Initializes Python's logging with the requested level.
    - If `structlog` is installed, configures it with a filtering bound logger.
    - Sets DEBUG level for MCP protocol libraries for detailed debugging.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format=("%(asctime)s %(levelname)s %(name)s - %(message)s"),
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Enable DEBUG logging for MCP protocol libraries to see detailed protocol
    # messages, session management, and transport-level communication
    mcp_loggers = [
        "mcp",
        "mcp.server",
        "mcp.server.sse",
        "mcp.server.lowlevel",
        "mcp.server.lowlevel.server",
        "fastapi_mcp",
        "fastapi_mcp.server",
        "sse_starlette",
    ]
    for logger_name in mcp_loggers:
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

    try:  # optional structlog
        structlog = importlib.import_module("structlog")
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        )
    except ModuleNotFoundError:  # pragma: no cover
        pass
