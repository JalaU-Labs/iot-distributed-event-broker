"""Unit tests for the broker wake-up waiter."""

from __future__ import annotations

import httpx

from iot_system.infrastructure.config import WakeUpConfig
from iot_system.infrastructure.wakeup import BrokerWakeUpWaiter


def _config(**overrides: object) -> WakeUpConfig:
    defaults: dict[str, object] = {
        "_env_file": None,
        "enabled": True,
        "url": "https://example.com/health",
        "timeout_seconds": 5.0,
        "interval_seconds": 0.01,
        "request_timeout_seconds": 1.0,
    }
    defaults.update(overrides)
    return WakeUpConfig(**defaults)  # type: ignore[arg-type]


async def test_returns_true_when_disabled() -> None:
    config = _config(enabled=False)
    waiter = BrokerWakeUpWaiter(config)
    assert await waiter.wait_until_ready() is True


async def test_returns_true_when_url_empty() -> None:
    config = _config(url="")
    waiter = BrokerWakeUpWaiter(config)
    assert await waiter.wait_until_ready() is True


async def test_returns_true_on_immediate_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        waiter = BrokerWakeUpWaiter(_config(), client=client)
        assert await waiter.wait_until_ready() is True


async def test_retries_until_ok() -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, text="OK")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        waiter = BrokerWakeUpWaiter(_config(), client=client)
        assert await waiter.wait_until_ready() is True
        assert attempts["n"] == 3


async def test_returns_false_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("always down", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        waiter = BrokerWakeUpWaiter(
            _config(timeout_seconds=0.05, interval_seconds=0.01),
            client=client,
        )
        assert await waiter.wait_until_ready() is False


async def test_returns_false_when_body_is_not_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not the right body")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        waiter = BrokerWakeUpWaiter(
            _config(timeout_seconds=0.05, interval_seconds=0.01),
            client=client,
        )
        assert await waiter.wait_until_ready() is False


async def test_returns_false_on_non_200_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        waiter = BrokerWakeUpWaiter(
            _config(timeout_seconds=0.05, interval_seconds=0.01),
            client=client,
        )
        assert await waiter.wait_until_ready() is False


async def test_aclose_does_not_close_injected_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="OK")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        waiter = BrokerWakeUpWaiter(_config(), client=client)
        await waiter.aclose()
        # The injected client must remain usable because the waiter does not own it.
        response = await client.get("https://example.com")
        assert response.status_code == 200
