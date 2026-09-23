"""Open-Meteo weather provider.

Implements WeatherProviderProtocol using the public, key-less Open-Meteo API.
Temperature lookups are cached with a TTL to avoid hammering the API, and
transient HTTP failures are retried with exponential backoff.
"""

from __future__ import annotations

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from iot_system.infrastructure.cache import TTLCache
from iot_system.infrastructure.config import WeatherConfig
from iot_system.infrastructure.logging import get_logger

logger = get_logger(__name__)


class WeatherProviderError(RuntimeError):
    """Raised when the weather provider cannot fetch a temperature."""


class OpenMeteoWeatherProvider:
    """Fetches current temperature from Open-Meteo with caching and retries.

    The provider is safe to share across coroutines: the HTTP client is
    async-native and the cache serializes concurrent lookups per coordinate.
    """

    def __init__(
        self,
        config: WeatherConfig,
        client: httpx.AsyncClient | None = None,
        cache: TTLCache[tuple[float, float], float] | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._owns_client = client is None
        self._cache: TTLCache[tuple[float, float], float] = cache or TTLCache(
            ttl_seconds=float(config.cache_ttl_seconds),
        )

    async def __aenter__(self) -> OpenMeteoWeatherProvider:
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._config.request_timeout_seconds,
            )
        return self._client

    async def aclose(self) -> None:
        """Close the HTTP client if this instance owns it."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_temperature_celsius(
        self,
        latitude: float,
        longitude: float,
    ) -> float:
        """Return the current temperature for the given coordinates.

        Results are cached for ``cache_ttl_seconds``. Concurrent calls for
        the same coordinates share a single in-flight request.
        """
        key = (latitude, longitude)

        async def fetch() -> float:
            return await self._fetch_temperature(latitude, longitude)

        return await self._cache.get_or_set(key, fetch)

    async def _fetch_temperature(
        self,
        latitude: float,
        longitude: float,
    ) -> float:
        client = await self._ensure_client()
        params: dict[str, str | float] = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m",
            "timezone": "UTC",
        }

        data: dict[str, object]
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._config.max_retries + 1),
                wait=wait_exponential(
                    multiplier=self._config.initial_retry_wait_seconds,
                    min=self._config.initial_retry_wait_seconds,
                    max=30.0,
                ),
                retry=retry_if_exception_type(httpx.HTTPError),
                reraise=True,
            ):
                with attempt:
                    response = await client.get(self._config.api_url, params=params)
                    response.raise_for_status()
                    data = response.json()
        except httpx.HTTPError as exc:
            raise WeatherProviderError(
                f"Failed to fetch weather after " f"{self._config.max_retries + 1} attempts: {exc}"
            ) from exc

        current = data.get("current", {})
        if not isinstance(current, dict):
            raise WeatherProviderError("Open-Meteo response has an invalid 'current' field")

        temperature = current.get("temperature_2m")
        if temperature is None:
            raise WeatherProviderError("Open-Meteo response is missing 'current.temperature_2m'")

        logger.debug(
            "weather.fetched",
            latitude=latitude,
            longitude=longitude,
            temperature_celsius=temperature,
        )
        return float(temperature)
