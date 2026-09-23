"""Domain protocols (structural interfaces).

These protocols implement the Dependency Inversion Principle (the `D` in
SOLID): the domain and application layers depend on these abstractions,
while the infrastructure layer provides the concrete implementations.

Structural typing (PEP 544) is used instead of classical inheritance so
that any class exposing the right methods satisfies the contract, which
simplifies testing and decoupling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from iot_system.domain.entities import SensorReading


@runtime_checkable
class ClockProtocol(Protocol):
    """Provides the current time. Injected to make time deterministic in tests."""

    def now(self) -> datetime:
        """Return the current, timezone-aware datetime."""
        ...


@runtime_checkable
class WeatherProviderProtocol(Protocol):
    """Fetches the current temperature for a geographic coordinate."""

    async def get_temperature_celsius(
        self,
        latitude: float,
        longitude: float,
    ) -> float:
        """Return the current temperature in Celsius for the given location."""
        ...


@runtime_checkable
class MQTTPublisherProtocol(Protocol):
    """Minimal MQTT publishing contract required by the application layer."""

    async def connect(self) -> None:
        """Open the connection to the broker."""
        ...

    async def disconnect(self) -> None:
        """Close the connection to the broker gracefully."""
        ...

    async def publish(
        self,
        topic: str,
        payload: bytes,
        qos: int,
        retain: bool = False,
    ) -> None:
        """Publish a payload to the given topic with the specified QoS."""
        ...


@runtime_checkable
class SerializerProtocol(Protocol):
    """Serializes and deserializes domain entities to/from bytes.

    Separating serialization from the entities keeps the domain free of
    any dependency on JSON, MessagePack, or any other encoding.
    """

    def encode(self, reading: SensorReading) -> bytes:
        """Serialize a SensorReading to bytes."""
        ...

    def decode(self, payload: bytes) -> SensorReading:
        """Deserialize bytes into a SensorReading."""
        ...


@runtime_checkable
class RandomProtocol(Protocol):
    """Minimal source of randomness required by the publisher.

    Narrowing the dependency to the single method the application actually
    uses keeps the contract honest (Interface Segregation Principle) and
    allows deterministic fakes in tests without subclassing ``random.Random``.
    """

    def uniform(self, a: float, b: float) -> float:
        """Return a random float N such that a <= N <= b."""
        ...
