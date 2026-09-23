"""Serialization adapters for domain entities.

This module isolates the encoding concern from the domain. Entities remain
unaware of JSON, MessagePack, or any other wire format.
"""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from iot_system.domain.entities import SensorReading


class SerializationError(ValueError):
    """Raised when a payload cannot be encoded or decoded."""


class JsonSensorReadingSerializer:
    """JSON serializer for SensorReading.

    The wire format is a flat JSON object with UTF-8 encoding:

    .. code-block:: json

        {
          "reading_id": "0f8fad5b-d9cb-469f-a165-70867728950e",
          "device_id": "sensor-001",
          "temperature_celsius": 22.5,
          "timestamp": "2026-09-22T18:00:00+00:00"
        }

    Explicit field mapping is used instead of ``dataclasses.asdict`` so the
    wire contract is versioned and stable even if the entity evolves.
    """

    def encode(self, reading: SensorReading) -> bytes:
        """Serialize a SensorReading into UTF-8 JSON bytes."""
        payload = {
            "reading_id": str(reading.reading_id),
            "device_id": reading.device_id,
            "temperature_celsius": reading.temperature_celsius,
            "timestamp": reading.timestamp.isoformat(),
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    def decode(self, payload: bytes) -> SensorReading:
        """Deserialize UTF-8 JSON bytes into a SensorReading.

        Raises:
            SerializationError: if the payload is not valid JSON, is not an
                object, or is missing required fields.
        """
        try:
            data = json.loads(payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SerializationError(f"Invalid JSON payload: {exc}") from exc

        if not isinstance(data, dict):
            raise SerializationError("Payload must be a JSON object")

        try:
            return SensorReading(
                device_id=str(data["device_id"]),
                temperature_celsius=float(data["temperature_celsius"]),
                timestamp=datetime.fromisoformat(str(data["timestamp"])),
                reading_id=UUID(str(data["reading_id"])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SerializationError(f"Invalid SensorReading payload: {exc}") from exc
