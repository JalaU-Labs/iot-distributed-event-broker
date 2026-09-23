"""Unit tests for the aiomqtt publisher adapter.

The tests replace ``aiomqtt.Client`` with a lightweight async context
manager that records publish operations, avoiding any real network I/O.
"""

from __future__ import annotations

from typing import Any

import pytest

from iot_system.infrastructure.config import MQTTConfig
from iot_system.infrastructure.mqtt import AiomqttPublisher, MQTTConnectionError


class MockMQTTClient:
    """Minimal async context manager that mimics aiomqtt.Client."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.published: list[tuple[str, bytes, int, bool]] = []
        self.connected = False

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


@pytest.fixture
def websocket_config() -> MQTTConfig:
    return MQTTConfig(
        broker_host="test.example.com",
        broker_port=8883,
        transport="websockets",
        use_tls=True,
        ws_path="/mqtt",
    )


@pytest.fixture
def tcp_config() -> MQTTConfig:
    return MQTTConfig(
        broker_host="localhost",
        broker_port=1883,
        transport="tcp",
        use_tls=False,
    )


async def test_connect_uses_websocket_transport(
    websocket_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, MockMQTTClient] = {}

    def client_factory(**kwargs: Any) -> MockMQTTClient:
        client = MockMQTTClient(**kwargs)
        captured["client"] = client
        return client

    monkeypatch.setattr("iot_system.infrastructure.mqtt.aiomqtt.Client", client_factory)

    publisher = AiomqttPublisher(websocket_config)
    await publisher.connect()
    assert captured["client"].kwargs["transport"] == "websockets"
    assert captured["client"].kwargs["hostname"] == "test.example.com"
    assert captured["client"].kwargs["port"] == 8883
    assert captured["client"].kwargs["websocket_path"] == "/mqtt"
    assert captured["client"].kwargs["tls_context"] is not None
    await publisher.disconnect()


async def test_connect_uses_tcp_transport_without_tls(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, MockMQTTClient] = {}

    def client_factory(**kwargs: Any) -> MockMQTTClient:
        client = MockMQTTClient(**kwargs)
        captured["client"] = client
        return client

    monkeypatch.setattr("iot_system.infrastructure.mqtt.aiomqtt.Client", client_factory)

    publisher = AiomqttPublisher(tcp_config)
    await publisher.connect()
    assert captured["client"].kwargs["transport"] == "tcp"
    assert captured["client"].kwargs["tls_context"] is None
    assert captured["client"].kwargs["websocket_path"] is None
    await publisher.disconnect()


async def test_publish_forwards_payload_and_qos(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, MockMQTTClient] = {}

    def client_factory(**kwargs: Any) -> MockMQTTClient:
        client = MockMQTTClient(**kwargs)
        captured["client"] = client
        return client

    monkeypatch.setattr("iot_system.infrastructure.mqtt.aiomqtt.Client", client_factory)

    publisher = AiomqttPublisher(tcp_config)
    await publisher.connect()
    await publisher.publish("iot/sensors/sensor-001/temperature", b'{"x":1}', qos=0)
    await publisher.publish("iot/sensors/sensor-001/alert", b'{"x":2}', qos=2, retain=True)

    assert captured["client"].published == [
        ("iot/sensors/sensor-001/temperature", b'{"x":1}', 0, False),
        ("iot/sensors/sensor-001/alert", b'{"x":2}', 2, True),
    ]
    await publisher.disconnect()


async def test_publish_before_connect_raises(tcp_config: MQTTConfig) -> None:
    publisher = AiomqttPublisher(tcp_config)
    with pytest.raises(MQTTConnectionError, match="Not connected"):
        await publisher.publish("any/topic", b"payload", qos=0)


async def test_disconnect_is_idempotent(
    tcp_config: MQTTConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "iot_system.infrastructure.mqtt.aiomqtt.Client",
        lambda **kwargs: MockMQTTClient(**kwargs),
    )
    publisher = AiomqttPublisher(tcp_config)
    await publisher.connect()
    await publisher.disconnect()
    await publisher.disconnect()  # must not raise
