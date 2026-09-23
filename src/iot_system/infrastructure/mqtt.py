"""MQTT publisher adapter backed by aiomqtt.

Wraps aiomqtt.Client with lifecycle management (connect/disconnect) and a
narrow publishing API. Supports both plain TCP (local Docker broker) and
WebSocket transport with TLS (Render broker).

Only the operations required by the application layer are exposed; the
adapter implements MQTTPublisherProtocol structurally.
"""

from __future__ import annotations

import ssl
from contextlib import AsyncExitStack

import aiomqtt

from iot_system.infrastructure.config import MQTTConfig
from iot_system.infrastructure.logging import get_logger

logger = get_logger(__name__)


class MQTTConnectionError(RuntimeError):
    """Raised when the MQTT client cannot connect or publish."""


class AiomqttPublisher:
    """Async MQTT publisher.

    The connection is opened lazily by ``connect`` and closed by
    ``disconnect``. The instance is not safe to share across event loops;
    each process should create its own publisher.
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

    def _build_tls_context(self) -> ssl.SSLContext:
        """Create a default TLS context.

        Render terminates TLS at the edge with a valid certificate chain, so
        the default context (which verifies certificates and hostnames) is
        sufficient.
        """
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
            # The connection is no longer usable; force a reconnect on next use.
            self._client = None
            raise MQTTConnectionError(f"Publish to {topic!r} failed: {exc}") from exc

        logger.debug(
            "mqtt.published",
            topic=topic,
            qos=qos,
            retain=retain,
            payload_size=len(payload),
        )
