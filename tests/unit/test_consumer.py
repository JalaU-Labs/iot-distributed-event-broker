"""Unit tests for the SensorConsumer use case."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from iot_system.application.consumer import SensorConsumer
from iot_system.domain.entities import SensorReading
from iot_system.domain.interfaces import IncomingMessage
from iot_system.infrastructure.serialization import JsonSensorReadingSerializer


class _FakeSubscriber:
    """In-memory MQTTSubscriberProtocol implementation."""

    def __init__(self, messages: list[IncomingMessage]) -> None:
        self._messages = messages
        self.connected = False
        self.subscriptions: list[tuple[str, int]] = []

    async def connect(self) -> None:
        self.connected = True

    async def connect_with_retry(self) -> None:
        await self.connect()

    async def disconnect(self) -> None:
        self.connected = False

    async def subscribe(self, topic: str, qos: int) -> None:
        self.subscriptions.append((topic, qos))

    async def messages(self) -> AsyncIterator[IncomingMessage]:
        for message in self._messages:
            yield message
            await asyncio.sleep(0)


def _encode_reading(
    device_id: str,
    temperature: float,
) -> bytes:
    serializer = JsonSensorReadingSerializer()
    return serializer.encode(
        SensorReading(
            device_id=device_id,
            temperature_celsius=temperature,
            timestamp=datetime(2026, 9, 22, 18, 0, 0, tzinfo=UTC),
        )
    )


async def test_consumer_subscribes_with_expected_qos() -> None:
    subscriber = _FakeSubscriber(messages=[])
    consumer = SensorConsumer(
        subscriber=subscriber,
        serializer=JsonSensorReadingSerializer(),
        telemetry_topic="iot/sensors/+/temperature",
        alert_topic="iot/sensors/+/alert",
    )
    stop_event = asyncio.Event()
    await consumer.run_forever(stop_event)
    assert subscriber.subscriptions == [
        ("iot/sensors/+/temperature", 0),
        ("iot/sensors/+/alert", 2),
    ]


async def test_consumer_counts_telemetry_and_alerts() -> None:
    messages = [
        IncomingMessage(
            topic="iot/sensors/sensor-001/temperature",
            payload=_encode_reading("sensor-001", 22.0),
            qos=0,
        ),
        IncomingMessage(
            topic="iot/sensors/sensor-002/alert",
            payload=_encode_reading("sensor-002", 45.0),
            qos=2,
        ),
        IncomingMessage(
            topic="iot/sensors/sensor-001/temperature",
            payload=_encode_reading("sensor-001", 23.0),
            qos=0,
        ),
    ]
    subscriber = _FakeSubscriber(messages=messages)
    consumer = SensorConsumer(
        subscriber=subscriber,
        serializer=JsonSensorReadingSerializer(),
        telemetry_topic="iot/sensors/+/temperature",
        alert_topic="iot/sensors/+/alert",
    )

    stop_event = asyncio.Event()
    await consumer.run_forever(stop_event)

    stats = consumer.stats
    assert stats.telemetry_received == 2
    assert stats.alerts_received == 1
    assert stats.decode_failures == 0
    assert stats.total == 3


async def test_consumer_counts_decode_failures() -> None:
    messages = [
        IncomingMessage(
            topic="iot/sensors/sensor-001/temperature",
            payload=b"not json",
            qos=0,
        ),
        IncomingMessage(
            topic="iot/sensors/sensor-001/temperature",
            payload=_encode_reading("sensor-001", 20.0),
            qos=0,
        ),
    ]
    subscriber = _FakeSubscriber(messages=messages)
    consumer = SensorConsumer(
        subscriber=subscriber,
        serializer=JsonSensorReadingSerializer(),
        telemetry_topic="iot/sensors/+/temperature",
        alert_topic="iot/sensors/+/alert",
    )

    stop_event = asyncio.Event()
    await consumer.run_forever(stop_event)

    stats = consumer.stats
    assert stats.telemetry_received == 1
    assert stats.decode_failures == 1


def test_consumer_rejects_empty_topics() -> None:
    with pytest.raises(ValueError, match="telemetry_topic"):
        SensorConsumer(
            subscriber=_FakeSubscriber(messages=[]),
            serializer=JsonSensorReadingSerializer(),
            telemetry_topic="",
            alert_topic="iot/sensors/+/alert",
        )
    with pytest.raises(ValueError, match="alert_topic"):
        SensorConsumer(
            subscriber=_FakeSubscriber(messages=[]),
            serializer=JsonSensorReadingSerializer(),
            telemetry_topic="iot/sensors/+/temperature",
            alert_topic="  ",
        )


async def test_consumer_stops_when_stop_event_is_set_during_idle() -> None:
    """The consumer must exit even if no new messages arrive."""
    subscriber = _FakeSubscriber(messages=[])
    consumer = SensorConsumer(
        subscriber=subscriber,
        serializer=JsonSensorReadingSerializer(),
        telemetry_topic="iot/sensors/+/temperature",
        alert_topic="iot/sensors/+/alert",
    )
    stop_event = asyncio.Event()

    async def _trigger() -> None:
        await asyncio.sleep(0.02)
        stop_event.set()

    await asyncio.wait_for(
        asyncio.gather(consumer.run_forever(stop_event), _trigger()),
        timeout=1.0,
    )
    assert subscriber.connected is False
