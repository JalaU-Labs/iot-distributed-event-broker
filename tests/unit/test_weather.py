"""Unit tests for the Open-Meteo weather provider."""

from __future__ import annotations

import httpx
import pytest

from iot_system.infrastructure.cache import TTLCache
from iot_system.infrastructure.config import WeatherConfig
from iot_system.infrastructure.weather import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
)


def _config(**overrides: object) -> WeatherConfig:
    defaults: dict[str, object] = {
        "cache_ttl_seconds": 60,
        "max_retries": 3,
        "initial_retry_wait_seconds": 0.01,
    }
    defaults.update(overrides)
    return WeatherConfig(**defaults)  # type: ignore[arg-type]


async def test_get_temperature_returns_value() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"current": {"temperature_2m": 22.5}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenMeteoWeatherProvider(_config(), client=client)
        temp = await provider.get_temperature_celsius(4.6, -74.0)
        assert temp == 22.5


async def test_get_temperature_uses_cache() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"current": {"temperature_2m": 20.0}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenMeteoWeatherProvider(_config(), client=client)
        await provider.get_temperature_celsius(4.6, -74.0)
        await provider.get_temperature_celsius(4.6, -74.0)
        assert calls["n"] == 1


async def test_retries_on_transient_http_error() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json={"current": {"temperature_2m": 18.0}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenMeteoWeatherProvider(_config(), client=client)
        temp = await provider.get_temperature_celsius(4.6, -74.0)
        assert temp == 18.0
        assert calls["n"] == 3


async def test_raises_after_max_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("always down", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenMeteoWeatherProvider(_config(max_retries=1), client=client)
        with pytest.raises(WeatherProviderError, match="Failed to fetch weather"):
            await provider.get_temperature_celsius(4.6, -74.0)


async def test_raises_on_missing_temperature_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"current": {}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenMeteoWeatherProvider(_config(), client=client)
        with pytest.raises(WeatherProviderError, match="temperature_2m"):
            await provider.get_temperature_celsius(4.6, -74.0)


async def test_aclose_does_not_close_injected_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"current": {"temperature_2m": 1.0}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenMeteoWeatherProvider(_config(), client=client)
        await provider.aclose()
        # Injected client must remain open because the provider does not own it.
        response = await client.get("https://example.com")
        assert response.status_code == 200


async def test_cache_is_shared_across_calls() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"current": {"temperature_2m": 5.0}})

    transport = httpx.MockTransport(handler)
    cache: TTLCache[tuple[float, float], float] = TTLCache(ttl_seconds=60.0)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenMeteoWeatherProvider(_config(), client=client, cache=cache)
        await provider.get_temperature_celsius(4.6, -74.0)
        await provider.get_temperature_celsius(4.6, -74.0)
        assert calls["n"] == 1
