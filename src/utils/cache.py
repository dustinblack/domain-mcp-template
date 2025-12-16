"""Basic LRU cache utility.

This module provides a thin, typed wrapper over :class:`cachetools.LRUCache`
with a minimal API for `get`/`set`. The wrapper helps isolate the dependency
and makes it easy to evolve the cache behavior (TTL, metrics, async safety)
without changing callers.
"""

from __future__ import annotations

from collections.abc import Hashable
from typing import Generic, Optional, TypeVar

from cachetools import LRUCache  # type: ignore[import-untyped]

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class Cache(Generic[K, V]):
    """Simple LRU cache.

    Parameters
    ----------
    maxsize: int
        Maximum number of entries to retain.
        When the cache is full, the least-recently-used entry is discarded.
    """

    def __init__(self, maxsize: int = 1024) -> None:
        self._cache: LRUCache[K, V] = LRUCache(maxsize=maxsize)

    def get(self, key: K) -> Optional[V]:
        """Return value for `key` or None if missing."""
        return self._cache.get(key)

    def set(self, key: K, value: V) -> None:
        """Insert or update `key` with `value`."""
        self._cache[key] = value
