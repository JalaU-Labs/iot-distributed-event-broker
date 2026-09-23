"""MQTT client adapter backed by aiomqtt.

Wraps aiomqtt.Client with lifecycle management (connect/disconnect),
publishing, and subscription. Supports both plain TCP (local Docker broker)
and WebSocket transport with TLS (Render broker).

The class implements MQTTPublisherProtocol and MQTTSubscriberProtocol
structurally. Consumers that only need to publish receive a reference
typed as the publisher protocol, and vice versa, so each use case sees
only the contract it requires (Interface Segregation Principle).
"""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack

import aiomqtt

from iot_system.domain.interfaces import IncomingMessage
from iot_system.infrastructure.config import MQTTConfig
from iot_system.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MQTTConnectionError(RuntimeError):
    """Raised when the MQTT client cannot connect, publish, or subscribe."""


class AiomqttClient:
    """Async MQTT client supporting publish and subscribe operations.

    The connection is opened by ``connect`` and closed by ``disconnect``.
    The instance is not safe to share across event loops; each process
    should create its own client.
    """

    def __init__(self, config: MQTTConfig) -> None:
        self._config = config
        self._client: aiomqtt.Client | None = None
        self._stack: AsyncExitStack | None = None

    async def connect(self) -> None:
        """Open the connection to the broker.

        Raises:
            MQTTConnectionError: if the handshake with the broker fails.
        """
        if self._client is not None:
            return

        stack = AsyncExitStack()
        try:
            client = aiomqtt.Client(
                hostname=self._config.broker_host,
                port=self._config.broker_port,
                username=self._config.username or None,
                password=self._config.password or None,
                keepalive=self._config.keepalive_seconds,
                transport="websockets" if self._config.transport == "websockets" else "tcp",
                tls_context=self._build_tls_context() if self._config.use_tls else None,
                websocket_path=self._config.ws_path or None,
                timeout=10.0,
            )
            await stack.enter_async_context(client)
        except Exception as exc:  # noqa: BLE001 - wrapped into a domain-specific error
            await stack.aclose()
            raise MQTTConnectionError(
                f"Failed to connect to "
                f"{self._config.broker_host}:{self._config.broker_port} "
                f"over {self._config.transport}: {exc}"
            ) from exc

        self._client = client
        self._stack = stack
        logger.info(
            "mqtt.connected",
            host=self._config.broker_host,
            port=self._config.broker_port,
            transport=self._config.transport,
            tls=self._config.use_tls,
        )

    async def connect_with_retry(
        self,
        *,
        max_attempts: int = 5,
        initial_delay_seconds: float = 1.0,
        max_delay_seconds: float = 30.0,
    ) -> None:
        """Attempt to connect with exponential backoff.

        This is essential when the broker is starting up (local Docker) or
        waking up from inactivity (Render free tier, ~30 s cold start).
        Raises the last ``MQTTConnectionError`` after exhausting attempts.
        """
        delay = initial_delay_seconds
        last_error: MQTTConnectionError | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                await self.connect()
                return
            except MQTTConnectionError as exc:
                last_error = exc
                if attempt == max_attempts:
                    break
                logger.warning(
                    "mqtt.connect_retry",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    delay_seconds=delay,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay_seconds)

        assert last_error is not None
        raise MQTTConnectionError(
            f"Could not connect to "
            f"{self._config.broker_host}:{self._config.broker_port} "
            f"after {max_attempts} attempts"
        ) from last_error

    def _build_tls_context(self) -> ssl.SSLContext:
        """Create a default TLS context that verifies certificates."""
        return ssl.create_default_context()

    async def disconnect(self) -> None:
        """Close the connection. Idempotent."""
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self._client = None
        logger.info("mqtt.disconnected")

    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool = False,
    ) -> None:
        """Publish a payload to the given topic.

        Raises:
            MQTTConnectionError: if the client is not connected, or if the
                broker rejects the publish operation.
        """
        if self._client is None:
            raise MQTTConnectionError("Not connected. Call connect() before publish().")

        try:
            await self._client.publish(topic, payload, qos=qos, retain=retain)
        except aiomqtt.MqttError as exc:
            self._client = None
            raise MQTTConnectionError(f"Publish to {topic!r} failed: {exc}") from exc

        logger.debug(
            "mqtt.published",
            topic=topic,
            qos=qos,
            retain=retain,
            payload_size=len(payload),
        )

    async def subscribe(self, topic: str, qos: int) -> None:
        """Subscribe to the given topic at the specified QoS level.

        Raises:
            MQTTConnectionError: if the client is not connected, or if the
                broker rejects the subscription.
        """
        if self._client is None:
            raise MQTTConnectionError("Not connected. Call connect() before subscribe().")

        try:
            await self._client.subscribe(topic, qos=qos)
        except aiomqtt.MqttError as exc:
            raise MQTTConnectionError(f"Subscribe to {topic!r} failed: {exc}") from exc

        logger.info("mqtt.subscribed", topic=topic, qos=qos)

    async def messages(self) -> AsyncIterator[IncomingMessage]:
        """Yield incoming messages until the connection is closed.

        Raises:
            MQTTConnectionError: if the client is not connected.
        """
        if self._client is None:
            raise MQTTConnectionError("Not connected. Call connect() before consuming.")

        async for message in self._client.messages:
            yield IncomingMessage(
                topic=str(message.topic),
                payload=bytes(message.payload),
                qos=int(message.qos),
            )
