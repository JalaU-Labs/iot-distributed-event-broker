"""Unit tests for the JSON SensorReading serializer."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from iot_system.domain.entities import SensorReading
from iot_system.infrastructure.serialization import (
    JsonSensorReadingSerializer,
    SerializationError,
)


@pytest.fixture
def reading() -> SensorReading:
    return SensorReading(
        device_id="sensor-001",
        temperature_celsius=22.5,
        timestamp=datetime(2026, 9, 22, 18, 0, 0, tzinfo=UTC),
        reading_id=UUID("0f8fad5b-d9cb-469f-a165-70867728950e"),
    )


def test_encode_produces_utf8_json_bytes(reading: SensorReading) -> None:
    serializer = JsonSensorReadingSerializer()
    payload = serializer.encode(reading)

    assert isinstance(payload, bytes)
    data = json.loads(payload.decode("utf-8"))
    assert data["device_id"] == "sensor-001"
    assert data["temperature_celsius"] == 22.5
    assert data["reading_id"] == "0f8fad5b-d9cb-469f-a165-70867728950e"
    assert data["timestamp"] == "2026-09-22T18:00:00+00:00"


def test_roundtrip_preserves_all_fields(reading: SensorReading) -> None:
    serializer = JsonSensorReadingSerializer()
    decoded = serializer.decode(serializer.encode(reading))

    assert decoded.device_id == reading.device_id
    assert decoded.temperature_celsius == reading.temperature_celsius
    assert decoded.timestamp == reading.timestamp
    assert decoded.reading_id == reading.reading_id


def test_decode_rejects_invalid_json() -> None:
    serializer = JsonSensorReadingSerializer()
    with pytest.raises(SerializationError, match="Invalid JSON"):
        serializer.decode(b"not json")


def test_decode_rejects_non_object_payload() -> None:
    serializer = JsonSensorReadingSerializer()
    with pytest.raises(SerializationError, match="JSON object"):
        serializer.decode(b"[1, 2, 3]")


def test_decode_rejects_missing_fields() -> None:
    serializer = JsonSensorReadingSerializer()
    with pytest.raises(SerializationError, match="Invalid SensorReading"):
        serializer.decode(b'{"device_id": "sensor-001"}')


def test_decode_rejects_invalid_timestamp() -> None:
    serializer = JsonSensorReadingSerializer()
    payload = (
        b'{"reading_id":"0f8fad5b-d9cb-469f-a165-70867728950e",'
        b'"device_id":"sensor-001","temperature_celsius":22.5,'
        b'"timestamp":"not-a-timestamp"}'
    )
    with pytest.raises(SerializationError, match="Invalid SensorReading"):
        serializer.decode(payload)
