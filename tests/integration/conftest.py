"""Shared fixtures for integration tests.

Integration tests exercise the platform against a real MQTT broker
running locally (see ``make up``). They are deselected by default via the
``integration`` marker; run them with ``make test-integration``.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import AsyncIterator

import pytest

from iot_system.infrastructure.config import Settings
from iot_system.infrastructure.mqtt import AiomqttClient


def _is_broker_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection to the broker succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Session-wide settings loaded from environment."""
    return Settings()


@pytest.fixture(scope="session", autouse=True)
def _skip_when_broker_unreachable(settings: Settings) -> None:
    """Skip the entire integration suite when the local broker is down."""
    if not _is_broker_reachable(settings.mqtt.broker_host, settings.mqtt.broker_port):
        pytest.skip(
            f"MQTT broker not reachable at "
            f"{settings.mqtt.broker_host}:{settings.mqtt.broker_port}. "
            f"Run 'make up' first.",
            allow_module_level=True,
        )


@pytest.fixture
def unique_prefix() -> str:
    """Isolated topic prefix per test to avoid cross-test interference."""
    return f"test/integration/{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def mqtt_client(settings: Settings) -> AsyncIterator[AiomqttClient]:
    """Provide a connected AiomqttClient, cleaned up after the test."""
    client = AiomqttClient(settings.mqtt)
    await client.connect()
    try:
        yield client
    finally:
        await client.disconnect()
