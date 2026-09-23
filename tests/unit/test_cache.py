"""Unit tests for the generic TTL cache."""

from __future__ import annotations

import asyncio

import pytest

from iot_system.infrastructure.cache import TTLCache


class _FakeClock:
    """Deterministic clock for TTL tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


async def test_get_returns_none_when_empty() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10.0)
    assert await cache.get("missing") is None


async def test_set_then_get_returns_value() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10.0)
    await cache.set("k", 42)
    assert await cache.get("k") == 42


async def test_entry_expires_after_ttl() -> None:
    clock = _FakeClock()
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=5.0, clock=clock)
    await cache.set("k", 1)
    clock.advance(4.9)
    assert await cache.get("k") == 1
    clock.advance(0.2)
    assert await cache.get("k") is None


async def test_invalidate_removes_entry() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10.0)
    await cache.set("k", 1)
    await cache.invalidate("k")
    assert await cache.get("k") is None


async def test_clear_removes_all_entries() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10.0)
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.clear()
    assert await cache.get("a") is None
    assert await cache.get("b") is None


async def test_get_or_set_invokes_factory_once() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10.0)
    calls = 0

    async def factory() -> int:
        nonlocal calls
        calls += 1
        return 7

    assert await cache.get_or_set("k", factory) == 7
    assert await cache.get_or_set("k", factory) == 7
    assert calls == 1


async def test_concurrent_get_or_set_shares_single_call() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10.0)
    calls = 0

    async def factory() -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)
        return 99

    results = await asyncio.gather(
        cache.get_or_set("k", factory),
        cache.get_or_set("k", factory),
        cache.get_or_set("k", factory),
    )
    assert list(results) == [99, 99, 99]
    assert calls == 1


async def test_ttl_must_be_positive() -> None:
    with pytest.raises(ValueError, match="ttl_seconds"):
        TTLCache(ttl_seconds=0.0)
