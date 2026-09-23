"""Application configuration loaded from environment variables.

Uses pydantic-settings to provide typed, validated configuration with
sensible defaults. No secrets are hardcoded; every value can be overridden
via environment variables or a local `.env` file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MQTTConfig(BaseSettings):
    """MQTT broker connection settings.

    Supports both plain TCP (local broker) and WebSocket/TLS (Render broker).
    """

    model_config = SettingsConfigDict(env_prefix="MQTT_", extra="ignore")

    broker_host: str = Field(default="localhost")
    broker_port: int = Field(default=1883, ge=1, le=65535)
    transport: Literal["tcp", "websockets"] = "tcp"
    use_tls: bool = False
    ws_path: str = ""
    username: str | None = None
    password: str | None = None
    qos_level: int = Field(default=1, ge=0, le=2)
    topic_prefix: str = "iot/sensors"
    keepalive_seconds: int = Field(default=60, gt=0)
    reconnect_interval_seconds: int = Field(default=5, gt=0)

    @field_validator("ws_path")
    @classmethod
    def _normalize_ws_path(cls, value: str) -> str:
        """Ensure a leading slash when the path is not empty."""
        if value and not value.startswith("/"):
            return f"/{value}"
        return value


class WeatherConfig(BaseSettings):
    """Open-Meteo weather API settings and cache policy."""

    model_config = SettingsConfigDict(env_prefix="WEATHER_", extra="ignore")

    api_url: str = "https://api.open-meteo.com/v1/forecast"
    latitude: float = Field(default=4.6097, ge=-90.0, le=90.0)
    longitude: float = Field(default=-74.0817, ge=-180.0, le=180.0)
    cache_ttl_seconds: int = Field(default=300, gt=0)
    request_timeout_seconds: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=10)
    initial_retry_wait_seconds: float = Field(default=1.0, gt=0)


class DeviceConfig(BaseSettings):
    """Simulated device settings."""

    model_config = SettingsConfigDict(env_prefix="DEVICE_", extra="ignore")

    device_id: str = "sensor-001"
    publish_interval_seconds: float = Field(default=2.0, gt=0)
    min_temperature_celsius: float = Field(default=15.0, ge=-100.0, le=100.0)
    max_temperature_celsius: float = Field(default=30.0, ge=-100.0, le=100.0)
    temperature_variation_celsius: float = Field(default=0.5, ge=0.0)

    @model_validator(mode="after")
    def _validate_range(self) -> DeviceConfig:
        """Ensure min is strictly less than max."""
        if self.min_temperature_celsius >= self.max_temperature_celsius:
            raise ValueError(
                f"min_temperature_celsius ({self.min_temperature_celsius}) "
                f"must be strictly less than max_temperature_celsius "
                f"({self.max_temperature_celsius})"
            )
        return self


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(env_prefix="LOG_", extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_format: bool = False


class Settings(BaseSettings):
    """Root settings aggregating all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    mqtt: MQTTConfig = Field(default_factory=MQTTConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached, singleton instance of the application settings.

    The cache can be cleared in tests with `get_settings.cache_clear()`.
    """
    return Settings()
