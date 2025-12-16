"""Lightweight correlation ID utilities for structured logging.

Provides a per-request correlation identifier via a ContextVar so that
async tasks spawned during a request can include the same ``req_id`` in
their log records. This supports end-to-end tracing across the HTTP layer
and upstream adapter calls without relying on global state.
"""

from __future__ import annotations

from contextvars import ContextVar

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(request_id: str) -> None:
    """Set the current request correlation id in a context variable."""

    _request_id_var.set(request_id)


def get_request_id() -> str:
    """Return the current request correlation id, or empty string."""

    return _request_id_var.get()
