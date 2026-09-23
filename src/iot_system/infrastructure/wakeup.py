"""Poll an external readiness endpoint before connecting to the broker.

In cloud deployments where the MQTT broker runs on a platform that sleeps
after inactivity (e.g. Render's free tier), a publisher or consumer may
try to connect before the broker is awake. This module provides a small
waiter that polls the health endpoint of a sibling service (the demo
publisher) until it returns ``200 OK`` with body ``OK``. Because the
demo publisher is itself connected to the broker, a healthy demo implies
a reachable broker.

The waiter is opt-in: it only runs when ``WAKEUP_ENABLED=true`` and
``WAKEUP_URL`` are set. It never raises on transient HTTP errors; it
simply retries until the configured timeout is exhausted.
"""

from __future__ import annotations

import asyncio
import time

import httpx

from iot_system.infrastructure.config import WakeUpConfig
from iot_system.infrastructure.logging import get_logger

logger = get_logger(__name__)


class BrokerWakeUpWaiter:
    """Poll a readiness URL until it responds 200 OK.

    The waiter is safe to share across coroutines; it owns its HTTP
    client unless one is injected.
    """

    def __init__(
        self,
        config: WakeUpConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> BrokerWakeUpWaiter:
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

    async def wait_until_ready(self) -> bool:
        """Poll the configured URL until it returns 200 OK with body ``OK``.

        Returns ``True`` immediately if the waiter is disabled or no URL
        is configured, so that local development is unaffected.
        """
        if not self._config.enabled or not self._config.url:
            logger.debug("wakeup.disabled")
            return True

        client = await self._ensure_client()
        deadline = time.monotonic() + self._config.timeout_seconds
        attempt = 0

        while time.monotonic() < deadline:
            attempt += 1
            try:
                response = await client.get(self._config.url)
                body = response.text.strip()
                if response.status_code == 200 and body == "OK":
                    logger.info(
                        "wakeup.ready",
                        url=self._config.url,
                        attempts=attempt,
                    )
                    return True
                logger.debug(
                    "wakeup.not_ready",
                    url=self._config.url,
                    status=response.status_code,
                    body=body[:64],
                )
            except httpx.HTTPError as exc:
                logger.debug(
                    "wakeup.request_failed",
                    url=self._config.url,
                    error=str(exc),
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sleep_for = min(self._config.interval_seconds, remaining)
            logger.info(
                "wakeup.waiting",
                url=self._config.url,
                attempt=attempt,
                remaining_seconds=round(remaining, 1),
            )
            await asyncio.sleep(sleep_for)

        logger.error(
            "wakeup.timeout",
            url=self._config.url,
            timeout_seconds=self._config.timeout_seconds,
            attempts=attempt,
        )
        return False
