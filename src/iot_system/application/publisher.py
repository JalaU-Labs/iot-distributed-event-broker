"""Sensor publisher use case.

Orchestrates the flow: fetch a base temperature from the weather provider,
build a SensorReading entity, serialize it, and publish to the appropriate
MQTT topics with differentiated QoS levels.

The publisher depends only on protocols (Dependency Inversion Principle),
so it is fully testable without any real broker, HTTP client, or clock.
"""

from __future__ import annotations

import asyncio
import json
import random
from contextlib import suppress
from typing import Final

from iot_system.application.topics import TopicFactory
from iot_system.domain.entities import (
    DeviceState,
    SensorReading,
    TemperatureThresholds,
)
from iot_system.domain.interfaces import (
    ClockProtocol,
    MQTTPublisherProtocol,
    RandomProtocol,
    SerializerProtocol,
    WeatherProviderProtocol,
)
from iot_system.infrastructure.logging import get_logger

logger = get_logger(__name__)

# QoS levels selected according to the lab requirements.
# - QOS_TELEMETRY: 0 (at most once). Periodic readings tolerate loss.
# - QOS_STATUS: 1 (at least once). Retained status; a rare duplicate is fine.
# - QOS_ALERT: 2 (exactly once). Out-of-range alerts must not be duplicated.
QOS_TELEMETRY: Final[int] = 0
QOS_STATUS: Final[int] = 1
QOS_ALERT: Final[int] = 2


class SensorPublisher:
    """Periodically reads weather, builds readings, and publishes to MQTT.

    Each cycle:
        1. Fetch a base temperature from the weather provider (cached).
        2. Apply small random variation to simulate a real sensor.
        3. Build a ``SensorReading`` entity.
        4. Publish the reading on the temperature topic with QoS 0.
        5. If out of range, publish the same payload on the alert topic
           with QoS 2.
        6. Publish the device status on the status topic with QoS 1,
           retained.

    All dependencies are injected; the class holds no global state.
    """

    def __init__(
        self,
        device_id: str,
        latitude: float,
        longitude: float,
        thresholds: TemperatureThresholds,
        publish_interval_seconds: float,
        temperature_variation_celsius: float,
        weather_provider: WeatherProviderProtocol,
        mqtt_publisher: MQTTPublisherProtocol,
        serializer: SerializerProtocol,
        clock: ClockProtocol,
        topic_factory: TopicFactory,
        rng: RandomProtocol | None = None,
    ) -> None:
        if publish_interval_seconds <= 0:
            raise ValueError("publish_interval_seconds must be strictly positive")
        if temperature_variation_celsius < 0:
            raise ValueError("temperature_variation_celsius must not be negative")
        if not device_id.strip():
            raise ValueError("device_id must not be empty")

        self._device_id = device_id
        self._latitude = latitude
        self._longitude = longitude
        self._thresholds = thresholds
        self._interval = publish_interval_seconds
        self._variation = temperature_variation_celsius
        self._weather = weather_provider
        self._mqtt = mqtt_publisher
        self._serializer = serializer
        self._clock = clock
        self._topics = topic_factory
        self._rng = rng or random.Random()

    async def run_once(self) -> SensorReading:
        """Execute one publish cycle and return the published reading.

        The same reading is published on the temperature topic with QoS 0
        and, when out of range, on the alert topic with QoS 2.
        """
        base_temperature = await self._weather.get_temperature_celsius(
            latitude=self._latitude,
            longitude=self._longitude,
        )
        temperature = base_temperature + self._rng.uniform(
            -self._variation,
            self._variation,
        )

        reading = SensorReading(
            device_id=self._device_id,
            temperature_celsius=round(temperature, 2),
            timestamp=self._clock.now(),
        )
        payload = self._serializer.encode(reading)

        await self._mqtt.publish(
            topic=self._topics.temperature(),
            payload=payload,
            qos=QOS_TELEMETRY,
            retain=False,
        )

        is_alert = reading.is_out_of_range(self._thresholds)
        if is_alert:
            await self._mqtt.publish(
                topic=self._topics.alert(),
                payload=payload,
                qos=QOS_ALERT,
                retain=False,
            )
            logger.warning(
                "publisher.alert",
                device_id=self._device_id,
                reading_id=str(reading.reading_id),
                temperature_celsius=reading.temperature_celsius,
                min_celsius=self._thresholds.min_celsius,
                max_celsius=self._thresholds.max_celsius,
            )
        else:
            logger.info(
                "publisher.telemetry",
                device_id=self._device_id,
                reading_id=str(reading.reading_id),
                temperature_celsius=reading.temperature_celsius,
            )

        await self._publish_status(DeviceState.ACTIVE)
        return reading

    async def _publish_status(self, state: DeviceState) -> None:
        """Publish the current device state on the status topic (retained)."""
        payload = json.dumps(
            {"device_id": self._device_id, "state": state.value},
            separators=(",", ":"),
        ).encode("utf-8")
        await self._mqtt.publish(
            topic=self._topics.status(),
            payload=payload,
            qos=QOS_STATUS,
            retain=True,
        )

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Publish readings periodically until ``stop_event`` is set.

        Any exception raised by ``run_once`` is logged and the loop
        continues; this keeps a transient weather API outage from killing
        the publisher. ``asyncio.CancelledError`` is re-raised to allow
        clean shutdown.
        """
        logger.info(
            "publisher.starting",
            device_id=self._device_id,
            interval_seconds=self._interval,
        )
        await self._mqtt.connect()
        try:
            while not stop_event.is_set():
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - defensive at the loop boundary
                    logger.error(
                        "publisher.cycle_failed",
                        device_id=self._device_id,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )

                with suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=self._interval)
        finally:
            await self._mqtt.disconnect()
            logger.info("publisher.stopped", device_id=self._device_id)
