"""Sensor consumer use case.

Subscribes to temperature and alert topics from all devices, deserializes
incoming payloads, and logs a structured summary. The consumer is
intentionally side-effect free beyond logging so it can be extended with
persistence or alerting without changing its core loop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Final

from iot_system.domain.interfaces import (
    MQTTSubscriberProtocol,
    SerializerProtocol,
)
from iot_system.infrastructure.logging import get_logger

logger = get_logger(__name__)

# QoS mirrors the publisher side: telemetry at 0, alerts at 2.
QOS_TELEMETRY: Final[int] = 0
QOS_ALERT: Final[int] = 2


@dataclass(frozen=True, slots=True)
class ConsumerStats:
    """Immutable snapshot of consumer counters."""

    telemetry_received: int
    alerts_received: int
    decode_failures: int

    @property
    def total(self) -> int:
        return self.telemetry_received + self.alerts_received + self.decode_failures


class SensorConsumer:
    """Subscribes to MQTT topics and processes incoming sensor readings.

    The consumer is protocol-agnostic: it receives a subscriber that
    satisfies MQTTSubscriberProtocol and a serializer that satisfies
    SerializerProtocol. It does not depend on aiomqtt, JSON, or any
    concrete infrastructure.
    """

    def __init__(
        self,
        subscriber: MQTTSubscriberProtocol,
        serializer: SerializerProtocol,
        telemetry_topic: str,
        alert_topic: str,
    ) -> None:
        if not telemetry_topic.strip():
            raise ValueError("telemetry_topic must not be empty")
        if not alert_topic.strip():
            raise ValueError("alert_topic must not be empty")

        self._subscriber = subscriber
        self._serializer = serializer
        self._telemetry_topic = telemetry_topic
        self._alert_topic = alert_topic
        # The subscription topic may contain wildcards (e.g. ``prefix/+/alert``),
        # so we match incoming topics by their last segment instead of exact
        # string equality.
        self._alert_channel = alert_topic.rsplit("/", 1)[-1]
        self._telemetry_received = 0
        self._alerts_received = 0
        self._decode_failures = 0

    @property
    def stats(self) -> ConsumerStats:
        return ConsumerStats(
            telemetry_received=self._telemetry_received,
            alerts_received=self._alerts_received,
            decode_failures=self._decode_failures,
        )

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Subscribe and process messages until ``stop_event`` is set.

        The subscription iterator is consumed in a separate task so that
        stopping does not require an incoming message: as soon as
        ``stop_event`` is set, both tasks are cancelled and the connection
        is closed.
        """
        logger.info(
            "consumer.starting",
            telemetry_topic=self._telemetry_topic,
            alert_topic=self._alert_topic,
        )
        await self._subscriber.connect()
        try:
            await self._subscriber.subscribe(self._telemetry_topic, qos=QOS_TELEMETRY)
            await self._subscriber.subscribe(self._alert_topic, qos=QOS_ALERT)

            consume_task = asyncio.create_task(self._consume())
            stop_task = asyncio.create_task(stop_event.wait())
            try:
                await asyncio.wait(
                    {consume_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                for task in (consume_task, stop_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(consume_task, stop_task, return_exceptions=True)
        finally:
            await self._subscriber.disconnect()
            logger.info(
                "consumer.stopped",
                telemetry_received=self._telemetry_received,
                alerts_received=self._alerts_received,
                decode_failures=self._decode_failures,
            )

    async def _consume(self) -> None:
        """Iterate over incoming messages until the iterator is exhausted."""
        async for message in self._subscriber.messages():
            self._handle(message.topic, message.payload)

    def _handle(self, topic: str, payload: bytes) -> None:
        """Decode and log a single incoming message."""
        try:
            reading = self._serializer.decode(payload)
        except Exception as exc:  # noqa: BLE001 - defensive at boundary
            self._decode_failures += 1
            logger.error(
                "consumer.decode_failed",
                topic=topic,
                error=str(exc),
                error_type=type(exc).__name__,
                payload_size=len(payload),
            )
            return

        channel = topic.rsplit("/", 1)[-1]
        if channel == self._alert_channel:
            self._alerts_received += 1
            logger.warning(
                "consumer.alert",
                topic=topic,
                device_id=reading.device_id,
                reading_id=str(reading.reading_id),
                temperature_celsius=reading.temperature_celsius,
            )
        else:
            self._telemetry_received += 1
            logger.info(
                "consumer.telemetry",
                topic=topic,
                device_id=reading.device_id,
                reading_id=str(reading.reading_id),
                temperature_celsius=reading.temperature_celsius,
            )
