"""Generic in-memory TTL cache.

This module provides a small, dependency-free async cache with per-key
expiration and per-key locking. It is safe for concurrent use within a
single asyncio event loop, which is the execution model of the application.

The cache uses double-checked locking to guarantee that concurrent callers
requesting the same missing key invoke the factory exactly once.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class _Entry(Generic[V]):
    """Internal cache entry with expiration metadata."""

    value: V
    expires_at: float


class TTLCache(Generic[K, V]):
    """In-memory cache with time-to-live per entry and per-key locking.

    Args:
        ttl_seconds: how long entries stay valid once stored. Must be > 0.
        clock: monotonic clock used to compute expiration. Injectable for tests.
    """

    def __init__(
        self,
        ttl_seconds: float,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be strictly positive")
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[K, _Entry[V]] = {}
        self._locks: dict[K, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get(self, key: K) -> V | None:
        """Return the cached value for the key, or None if missing or expired."""
        async with self._global_lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= self._clock():
                del self._entries[key]
                return None
            return entry.value

    async def set(self, key: K, value: V) -> None:
        """Store a value under the key with the configured TTL."""
        async with self._global_lock:
            self._entries[key] = _Entry(
                value=value,
                expires_at=self._clock() + self._ttl,
            )

    async def _get_key_lock(self, key: K) -> asyncio.Lock:
        async with self._global_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def get_or_set(
        self,
        key: K,
        factory: Callable[[], Awaitable[V]],
    ) -> V:
        """Return the cached value or compute-and-store it.

        Concurrent callers for the same key share a single factory invocation.
        Different keys proceed in parallel.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        key_lock = await self._get_key_lock(key)
        async with key_lock:
            # Double-checked locking: another coroutine may have populated
            # the cache while we were waiting for the per-key lock.
            cached = await self.get(key)
            if cached is not None:
                return cached
            value = await factory()
            await self.set(key, value)
            return value

    async def invalidate(self, key: K) -> None:
        """Remove an entry. The per-key lock is preserved for future use."""
        async with self._global_lock:
            self._entries.pop(key, None)

    async def clear(self) -> None:
        """Remove all entries."""
        async with self._global_lock:
            self._entries.clear()
