"""Unit tests for the SensorPublisher use case.

Dependencies are replaced by in-memory fakes, so the tests exercise the
orchestration logic without any I/O.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from iot_system.application.publisher import (
    QOS_ALERT,
    QOS_STATUS,
    QOS_TELEMETRY,
    SensorPublisher,
)
from iot_system.application.topics import TopicFactory
from iot_system.domain.entities import TemperatureThresholds
from iot_system.domain.interfaces import RandomProtocol
from iot_system.infrastructure.serialization import JsonSensorReadingSerializer


class _FixedClock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


class _FakeWeatherProvider:
    def __init__(self, temperature: float) -> None:
        self._temperature = temperature
        self.calls = 0

    async def get_temperature_celsius(
        self,
        latitude: float,
        longitude: float,
    ) -> float:
        self.calls += 1
        return self._temperature


class _RecordingMQTTPublisher:
    def __init__(self) -> None:
        self.connected = False
        self.published: list[tuple[str, bytes, int, bool]] = []

    async def connect(self) -> None:
        self.connected = True

    async def connect_with_retry(self) -> None:
        await self.connect()

    async def disconnect(self) -> None:
        self.connected = False

    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool = False,
    ) -> None:
        self.published.append((topic, payload, qos, retain))


class _NoVariationRandom:
    """Deterministic random source that always returns 0 from uniform(-a, a)."""

    def uniform(self, a: float, b: float) -> float:
        return 0.0


def _make_publisher(
    temperature: float,
    thresholds: TemperatureThresholds,
    rng: RandomProtocol | None = None,
) -> tuple[SensorPublisher, _RecordingMQTTPublisher, _FakeWeatherProvider]:
    mqtt = _RecordingMQTTPublisher()
    weather = _FakeWeatherProvider(temperature)
    publisher = SensorPublisher(
        device_id="sensor-001",
        latitude=4.6097,
        longitude=-74.0817,
        thresholds=thresholds,
        publish_interval_seconds=0.01,
        temperature_variation_celsius=0.5,
        weather_provider=weather,
        mqtt_publisher=mqtt,
        serializer=JsonSensorReadingSerializer(),
        clock=_FixedClock(datetime(2026, 9, 22, 18, 0, 0, tzinfo=UTC)),
        topic_factory=TopicFactory(prefix="iot/sensors", device_id="sensor-001"),
        rng=rng or _NoVariationRandom(),
    )
    return publisher, mqtt, weather


async def test_run_once_publishes_telemetry_and_status_on_normal_reading() -> None:
    thresholds = TemperatureThresholds(min_celsius=10.0, max_celsius=30.0)
    publisher, mqtt, weather = _make_publisher(temperature=22.0, thresholds=thresholds)

    reading = await publisher.run_once()

    assert weather.calls == 1
    assert reading.temperature_celsius == 22.0

    topics = [entry[0] for entry in mqtt.published]
    assert topics == [
        "iot/sensors/sensor-001/temperature",
        "iot/sensors/sensor-001/status",
    ]
    assert mqtt.published[0][2] == QOS_TELEMETRY
    assert mqtt.published[1][2] == QOS_STATUS
    assert mqtt.published[1][3] is True  # retained


async def test_run_once_publishes_alert_on_out_of_range_reading() -> None:
    thresholds = TemperatureThresholds(min_celsius=10.0, max_celsius=30.0)
    publisher, mqtt, _ = _make_publisher(temperature=45.0, thresholds=thresholds)

    reading = await publisher.run_once()

    assert reading.is_out_of_range(thresholds) is True
    topics = [entry[0] for entry in mqtt.published]
    assert topics == [
        "iot/sensors/sensor-001/temperature",
        "iot/sensors/sensor-001/alert",
        "iot/sensors/sensor-001/status",
    ]
    assert mqtt.published[1][2] == QOS_ALERT


async def test_reading_payload_roundtrips_via_serializer() -> None:
    thresholds = TemperatureThresholds(min_celsius=0.0, max_celsius=50.0)
    publisher, mqtt, _ = _make_publisher(temperature=25.0, thresholds=thresholds)

    reading = await publisher.run_once()

    payload = mqtt.published[0][1]
    decoded = JsonSensorReadingSerializer().decode(payload)
    assert decoded == reading


async def test_temperature_variation_applied() -> None:
    thresholds = TemperatureThresholds(min_celsius=0.0, max_celsius=50.0)
    publisher, _, _ = _make_publisher(temperature=20.0, thresholds=thresholds)

    # Default variation is 0.5, but the injected rng returns 0.0
    reading = await publisher.run_once()
    assert reading.temperature_celsius == 20.0


async def test_validation_rejects_negative_variation() -> None:
    with pytest.raises(ValueError, match="temperature_variation_celsius"):
        SensorPublisher(
            device_id="sensor-001",
            latitude=0.0,
            longitude=0.0,
            thresholds=TemperatureThresholds(min_celsius=0.0, max_celsius=1.0),
            publish_interval_seconds=1.0,
            temperature_variation_celsius=-0.1,
            weather_provider=_FakeWeatherProvider(0.0),
            mqtt_publisher=_RecordingMQTTPublisher(),
            serializer=JsonSensorReadingSerializer(),
            clock=_FixedClock(datetime(2026, 9, 22, tzinfo=UTC)),
            topic_factory=TopicFactory(prefix="x", device_id="sensor-001"),
        )


async def test_run_forever_connects_publishes_and_disconnects() -> None:
    thresholds = TemperatureThresholds(min_celsius=0.0, max_celsius=50.0)
    publisher, mqtt, _ = _make_publisher(temperature=20.0, thresholds=thresholds)

    stop_event = asyncio.Event()

    async def stopper() -> None:
        await asyncio.sleep(0.05)
        stop_event.set()

    await asyncio.gather(publisher.run_forever(stop_event), stopper())

    assert mqtt.connected is False
    assert mqtt.published  # at least one cycle ran
    assert mqtt.published[0][0].endswith("/temperature")


async def test_run_forever_continues_after_cycle_error() -> None:
    thresholds = TemperatureThresholds(min_celsius=0.0, max_celsius=50.0)

    class _FlakyWeather(_FakeWeatherProvider):
        def __init__(self) -> None:
            super().__init__(20.0)
            self._first = True

        async def get_temperature_celsius(
            self,
            latitude: float,
            longitude: float,
        ) -> float:
            if self._first:
                self._first = False
                raise RuntimeError("transient failure")
            return await super().get_temperature_celsius(latitude, longitude)

    mqtt = _RecordingMQTTPublisher()
    publisher = SensorPublisher(
        device_id="sensor-001",
        latitude=0.0,
        longitude=0.0,
        thresholds=thresholds,
        publish_interval_seconds=0.01,
        temperature_variation_celsius=0.0,
        weather_provider=_FlakyWeather(),
        mqtt_publisher=mqtt,
        serializer=JsonSensorReadingSerializer(),
        clock=_FixedClock(datetime(2026, 9, 22, tzinfo=UTC)),
        topic_factory=TopicFactory(prefix="iot/sensors", device_id="sensor-001"),
        rng=_NoVariationRandom(),
    )

    stop_event = asyncio.Event()

    async def stopper() -> None:
        await asyncio.sleep(0.08)
        stop_event.set()

    await asyncio.gather(publisher.run_forever(stop_event), stopper())

    assert mqtt.published  # the loop recovered after the failure
    assert mqtt.published[0][0].endswith("/temperature")
