"""Infrastructure layer: adapters for external systems.

This package contains concrete implementations of the domain protocols:
HTTP clients, MQTT clients, configuration loaders, logging setup, and
serializers. It depends on the domain layer, never the other way around.
"""

from iot_system.infrastructure.cache import TTLCache
from iot_system.infrastructure.clock import SystemClock
from iot_system.infrastructure.config import (
    DeviceConfig,
    LoggingConfig,
    MQTTConfig,
    Settings,
    WeatherConfig,
    get_settings,
)
from iot_system.infrastructure.health_server import HealthServer
from iot_system.infrastructure.logging import configure_logging, get_logger
from iot_system.infrastructure.mqtt import AiomqttClient, MQTTConnectionError
from iot_system.infrastructure.serialization import (
    JsonSensorReadingSerializer,
    SerializationError,
)
from iot_system.infrastructure.weather import (
    OpenMeteoWeatherProvider,
    WeatherProviderError,
)

__all__ = [
    "AiomqttClient",
    "DeviceConfig",
    "HealthServer",
    "JsonSensorReadingSerializer",
    "LoggingConfig",
    "MQTTConfig",
    "MQTTConnectionError",
    "OpenMeteoWeatherProvider",
    "SerializationError",
    "Settings",
    "SystemClock",
    "TTLCache",
    "WeatherConfig",
    "WeatherProviderError",
    "configure_logging",
    "get_logger",
    "get_settings",
]
