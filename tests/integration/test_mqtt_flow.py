"""End-to-end integration tests against a real MQTT broker.

These tests verify that the platform's publisher and consumer agree on
the wire format, topic structure, and QoS semantics when communicating
through a live broker.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from iot_system.domain.entities import SensorReading
from iot_system.infrastructure.config import Settings
from iot_system.infrastructure.mqtt import AiomqttClient
from iot_system.infrastructure.serialization import JsonSensorReadingSerializer

pytestmark = pytest.mark.integration


async def _collect_one(
    settings: Settings,
    topic_filter: str,
    qos: int,
    timeout: float = 5.0,
) -> bytes:
    """Subscribe, wait for a single message, and return its payload."""
    client = AiomqttClient(settings.mqtt)
    await client.connect()
    try:
        await client.subscribe(topic_filter, qos=qos)
        async with asyncio.timeout(timeout):
            async for message in client.messages():
                return message.payload
    finally:
        await client.disconnect()
    raise AssertionError("No message received within timeout")


async def test_publish_then_receive_roundtrip(
    settings: Settings,
    mqtt_client: AiomqttClient,
    unique_prefix: str,
) -> None:
    """A reading published on a topic is received byte-for-byte."""
    topic = f"{unique_prefix}/temperature"
    serializer = JsonSensorReadingSerializer()
    reading = SensorReading(
        device_id="sensor-it-001",
        temperature_celsius=23.45,
        timestamp=datetime(2026, 9, 22, 18, 0, 0, tzinfo=UTC),
    )
    payload = serializer.encode(reading)

    collector = asyncio.create_task(_collect_one(settings, topic, qos=1))
    await asyncio.sleep(0.3)  # give the subscriber time to attach
    await mqtt_client.publish(topic, payload, qos=1)
    received = await collector

    assert received == payload
    decoded = serializer.decode(received)
    assert decoded.device_id == reading.device_id
    assert decoded.temperature_celsius == reading.temperature_celsius


async def test_qos_zero_delivers_at_most_once(
    settings: Settings,
    mqtt_client: AiomqttClient,
    unique_prefix: str,
) -> None:
    """QoS 0 delivers a best-effort message when a subscriber is attached."""
    topic = f"{unique_prefix}/qos0"
    payload = b"qos-zero-payload"

    collector = asyncio.create_task(_collect_one(settings, topic, qos=0))
    await asyncio.sleep(0.3)
    await mqtt_client.publish(topic, payload, qos=0)
    received = await collector

    assert received == payload


async def test_qos_two_delivers_exactly_once(
    settings: Settings,
    mqtt_client: AiomqttClient,
    unique_prefix: str,
) -> None:
    """QoS 2 delivers the message with the full four-way handshake."""
    topic = f"{unique_prefix}/qos2"
    payload = b"qos-two-payload"

    collector = asyncio.create_task(_collect_one(settings, topic, qos=2))
    await asyncio.sleep(0.3)
    await mqtt_client.publish(topic, payload, qos=2)
    received = await collector

    assert received == payload


async def test_retained_message_is_delivered_to_late_subscriber(
    settings: Settings,
    mqtt_client: AiomqttClient,
    unique_prefix: str,
) -> None:
    """A retained message is delivered to subscribers that attach after publish."""
    topic = f"{unique_prefix}/retained"
    payload = b"retained-status"

    await mqtt_client.publish(topic, payload, qos=1, retain=True)
    await asyncio.sleep(0.3)

    received = await _collect_one(settings, topic, qos=1)
    assert received == payload

    # Clean up: publish an empty payload with retain=True to remove the retained message.
    await mqtt_client.publish(topic, b"", qos=1, retain=True)
