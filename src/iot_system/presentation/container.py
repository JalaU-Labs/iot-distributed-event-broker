"""Composition Root: wires settings and concrete adapters.

This module is the only place in the codebase where the concrete
implementations (aiomqtt, httpx, Open-Meteo) are instantiated and bound
to the application use cases. Tests can construct the container with
modified settings or override individual builders.
"""

from __future__ import annotations

from dataclasses import dataclass

from iot_system.application.consumer import SensorConsumer
from iot_system.application.publisher import SensorPublisher
from iot_system.application.topics import TopicFactory
from iot_system.domain.entities import TemperatureThresholds
from iot_system.infrastructure.clock import SystemClock
from iot_system.infrastructure.config import Settings
from iot_system.infrastructure.mqtt import AiomqttClient
from iot_system.infrastructure.serialization import JsonSensorReadingSerializer
from iot_system.infrastructure.weather import OpenMeteoWeatherProvider


@dataclass(frozen=True, slots=True)
class Container:
    """Builds fully-wired use case instances from a Settings object."""

    settings: Settings

    def build_publisher(self) -> SensorPublisher:
        """Assemble a SensorPublisher with all of its dependencies."""
        mqtt = AiomqttClient(self.settings.mqtt)
        weather = OpenMeteoWeatherProvider(self.settings.weather)
        thresholds = TemperatureThresholds(
            min_celsius=self.settings.device.min_temperature_celsius,
            max_celsius=self.settings.device.max_temperature_celsius,
        )
        topics = TopicFactory(
            prefix=self.settings.mqtt.topic_prefix,
            device_id=self.settings.device.device_id,
        )
        return SensorPublisher(
            device_id=self.settings.device.device_id,
            latitude=self.settings.weather.latitude,
            longitude=self.settings.weather.longitude,
            thresholds=thresholds,
            publish_interval_seconds=self.settings.device.publish_interval_seconds,
            temperature_variation_celsius=(self.settings.device.temperature_variation_celsius),
            weather_provider=weather,
            mqtt_publisher=mqtt,
            serializer=JsonSensorReadingSerializer(),
            clock=SystemClock(),
            topic_factory=topics,
        )

    def build_consumer(self) -> SensorConsumer:
        """Assemble a SensorConsumer with all of its dependencies."""
        mqtt = AiomqttClient(self.settings.mqtt)
        prefix = self.settings.mqtt.topic_prefix.rstrip("/")
        telemetry_topic = f"{prefix}/+/temperature"
        alert_topic = f"{prefix}/+/alert"
        return SensorConsumer(
            subscriber=mqtt,
            serializer=JsonSensorReadingSerializer(),
            telemetry_topic=telemetry_topic,
            alert_topic=alert_topic,
        )
