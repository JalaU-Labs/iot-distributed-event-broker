"""Domain layer: entities, value objects, and protocols.

This package has no dependencies on infrastructure, frameworks, or I/O.
It defines the vocabulary of the system.
"""

from iot_system.domain.entities import (
    DeviceState,
    SensorReading,
    TemperatureThresholds,
)
from iot_system.domain.interfaces import (
    ClockProtocol,
    IncomingMessage,
    MQTTPublisherProtocol,
    MQTTSubscriberProtocol,
    RandomProtocol,
    SerializerProtocol,
    WeatherProviderProtocol,
)

__all__ = [
    "ClockProtocol",
    "DeviceState",
    "IncomingMessage",
    "MQTTPublisherProtocol",
    "MQTTSubscriberProtocol",
    "RandomProtocol",
    "SensorReading",
    "SerializerProtocol",
    "TemperatureThresholds",
    "WeatherProviderProtocol",
]
