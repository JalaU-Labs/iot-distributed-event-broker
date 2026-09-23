"""Unit tests for configuration loading from environment and .env."""

from __future__ import annotations

from pathlib import Path

import pytest

from iot_system.infrastructure.config import MQTTConfig, Settings


def test_mqtt_config_reads_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MQTT_BROKER_HOST", "broker.example.com")
    monkeypatch.setenv("MQTT_BROKER_PORT", "8883")
    monkeypatch.setenv("MQTT_TRANSPORT", "websockets")
    monkeypatch.setenv("MQTT_USE_TLS", "true")
    config = MQTTConfig(_env_file=None)
    assert config.broker_host == "broker.example.com"
    assert config.broker_port == 8883
    assert config.transport == "websockets"
    assert config.use_tls is True


def test_settings_reads_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("MQTT_BROKER_HOST", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "MQTT_BROKER_HOST=from-dotenv\nMQTT_BROKER_PORT=9999\nDEVICE_DEVICE_ID=sensor-dotenv\n",
        encoding="utf-8",
    )
    settings = Settings()
    assert settings.mqtt.broker_host == "from-dotenv"
    assert settings.mqtt.broker_port == 9999
    assert settings.device.device_id == "sensor-dotenv"


def test_mqtt_config_isolated_from_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_env_file=None`` must skip the .env file entirely."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("MQTT_BROKER_HOST=ignored\n", encoding="utf-8")
    config = MQTTConfig(_env_file=None)
    assert config.broker_host == "localhost"
