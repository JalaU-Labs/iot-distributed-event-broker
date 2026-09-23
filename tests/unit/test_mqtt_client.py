"""Unit tests for the aiomqtt client adapter.

The tests replace ``aiomqtt.Client`` with a lightweight async context
manager that records publish and subscribe operations, avoiding any real
network I/O.
"""

from __future__ import annotations

from typing import Any

import pytest

from iot_system.infrastructure.config import MQTTConfig
from iot_system.infrastructure.mqtt import AiomqttClient, MQTTConnectionError


class MockMQTTClient:
    """Minimal async context manager that mimics aiomqtt.Client."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.published: list[tuple[str, bytes, int, bool]] = []
        self.subscriptions: list[tuple[str, int]] = []
        self.connected = False
        self.messages: list[Any] = []

    async def __aenter__(self) -> MockMQTTClient:
        self.connected = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.connected = False

    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        if not self.connected:
            raise RuntimeError("MockMQTTClient: publish called while disconnected")
        self.published.append((topic, payload, qos, retain))

    async def subscribe(self, topic: str, qos: int = 0) -> None:
        if not self.connected:
            raise RuntimeError("MockMQTTClient: subscribe called while disconnected")
        self.subscriptions.append((topic, qos))


@pytest.fixture
def websocket_config() -> MQTTConfig:
    return MQTTConfig(
        _env_file=None,
        broker_host="test.example.com",
        broker_port=8883,
        transport="websockets",
        use_tls=True,
        ws_path="/mqtt",
    )


@pytest.fixture
def tcp_config() -> MQTTConfig:
    return MQTTConfig(
        _env_file=None,
        broker_host="localhost",
        broker_port=1883,
        transport="tcp",
        use_tls=False,
        ws_path="",
    )


def _install_mock_client(monkeypatch: pytest.MonkeyPatch) -> dict[str, MockMQTTClient]:
    captured: dict[str, MockMQTTClient] = {}

    def factory(**kwargs: Any) -> MockMQTTClient:
        client = MockMQTTClient(**kwargs)
        captured["client"] = client
        return client

    monkeypatch.setattr("iot_system.infrastructure.mqtt.aiomqtt.Client", factory)
    return captured


async def test_connect_uses_websocket_transport(
    websocket_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install_mock_client(monkeypatch)
    client = AiomqttClient(websocket_config)
    await client.connect()
    assert captured["client"].kwargs["transport"] == "websockets"
    assert captured["client"].kwargs["hostname"] == "test.example.com"
    assert captured["client"].kwargs["port"] == 8883
    assert captured["client"].kwargs["websocket_path"] == "/mqtt"
    assert captured["client"].kwargs["tls_context"] is not None
    await client.disconnect()


async def test_connect_uses_tcp_transport_without_tls(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install_mock_client(monkeypatch)
    client = AiomqttClient(tcp_config)
    await client.connect()
    assert captured["client"].kwargs["transport"] == "tcp"
    assert captured["client"].kwargs["tls_context"] is None
    assert captured["client"].kwargs["websocket_path"] is None
    await client.disconnect()


async def test_publish_forwards_payload_and_qos(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install_mock_client(monkeypatch)
    client = AiomqttClient(tcp_config)
    await client.connect()
    await client.publish("iot/sensors/sensor-001/temperature", b'{"x":1}', qos=0)
    await client.publish("iot/sensors/sensor-001/alert", b'{"x":2}', qos=2, retain=True)

    assert captured["client"].published == [
        ("iot/sensors/sensor-001/temperature", b'{"x":1}', 0, False),
        ("iot/sensors/sensor-001/alert", b'{"x":2}', 2, True),
    ]
    await client.disconnect()


async def test_subscribe_forwards_topic_and_qos(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _install_mock_client(monkeypatch)
    client = AiomqttClient(tcp_config)
    await client.connect()
    await client.subscribe("iot/sensors/+/temperature", qos=0)
    await client.subscribe("iot/sensors/+/alert", qos=2)

    assert captured["client"].subscriptions == [
        ("iot/sensors/+/temperature", 0),
        ("iot/sensors/+/alert", 2),
    ]
    await client.disconnect()


async def test_publish_before_connect_raises(tcp_config: MQTTConfig) -> None:
    client = AiomqttClient(tcp_config)
    with pytest.raises(MQTTConnectionError, match="Not connected"):
        await client.publish("any/topic", b"payload", qos=0)


async def test_subscribe_before_connect_raises(tcp_config: MQTTConfig) -> None:
    client = AiomqttClient(tcp_config)
    with pytest.raises(MQTTConnectionError, match="Not connected"):
        await client.subscribe("any/topic", qos=0)


async def test_messages_before_connect_raises(tcp_config: MQTTConfig) -> None:
    client = AiomqttClient(tcp_config)
    with pytest.raises(MQTTConnectionError, match="Not connected"):
        async for _ in client.messages():
            pass


async def test_disconnect_is_idempotent(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_mock_client(monkeypatch)
    client = AiomqttClient(tcp_config)
    await client.connect()
    await client.disconnect()
    await client.disconnect()  # must not raise


async def test_connect_with_retry_succeeds_after_transient_failures(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"n": 0}

    def factory(**kwargs: Any) -> MockMQTTClient:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("connection refused")
        return MockMQTTClient(**kwargs)

    monkeypatch.setattr("iot_system.infrastructure.mqtt.aiomqtt.Client", factory)
    client = AiomqttClient(tcp_config)
    await client.connect_with_retry(
        max_attempts=3, initial_delay_seconds=0.01, max_delay_seconds=0.02
    )
    assert attempts["n"] == 3
    await client.disconnect()


async def test_connect_with_retry_raises_after_exhausting_attempts(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory(**kwargs: Any) -> MockMQTTClient:
        raise OSError("connection refused")

    monkeypatch.setattr("iot_system.infrastructure.mqtt.aiomqtt.Client", factory)
    client = AiomqttClient(tcp_config)
    with pytest.raises(MQTTConnectionError, match="after 3 attempts"):
        await client.connect_with_retry(
            max_attempts=3, initial_delay_seconds=0.01, max_delay_seconds=0.02
        )
