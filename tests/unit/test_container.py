"""Smoke tests for the Composition Root."""

from __future__ import annotations

from iot_system.application.consumer import SensorConsumer
from iot_system.application.publisher import SensorPublisher
from iot_system.infrastructure.config import Settings
from iot_system.presentation.container import Container


def test_build_publisher_returns_configured_instance() -> None:
    container = Container(Settings())
    publisher = container.build_publisher()
    assert isinstance(publisher, SensorPublisher)


def test_build_consumer_returns_configured_instance() -> None:
    container = Container(Settings())
    consumer = container.build_consumer()
    assert isinstance(consumer, SensorConsumer)


def test_build_publisher_uses_device_id_from_settings() -> None:
    settings = Settings()
    settings = settings.model_copy(
        update={
            "device": settings.device.model_copy(update={"device_id": "sensor-042"}),
        }
    )
    container = Container(settings)
    publisher = container.build_publisher()
    assert isinstance(publisher, SensorPublisher)
