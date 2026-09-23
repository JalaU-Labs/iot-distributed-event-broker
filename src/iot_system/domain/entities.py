"""Domain entities for the IoT event platform.

Entities are immutable value objects that represent the core concepts of the
domain. They have no dependency on any framework or infrastructure library
and are safe to pass across architectural boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class DeviceState(StrEnum):
    """Operational state of an IoT device."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TemperatureThresholds:
    """Allowed temperature range for a sensor.

    This is a value object: two instances with the same values are equal.
    """

    min_celsius: float
    max_celsius: float

    def __post_init__(self) -> None:
        if self.min_celsius >= self.max_celsius:
            raise ValueError(
                f"min_celsius ({self.min_celsius}) must be strictly less "
                f"than max_celsius ({self.max_celsius})"
            )

    def is_out_of_range(self, temperature: float) -> bool:
        """Return True if the given temperature lies outside the range."""
        return temperature < self.min_celsius or temperature > self.max_celsius


@dataclass(frozen=True, slots=True)
class SensorReading:
    """A single temperature measurement produced by an IoT sensor.

    The entity is self-validating: construction fails if the invariants are
    violated. The timestamp must be timezone-aware so that readings from
    devices in different timezones can be compared reliably.
    """

    device_id: str
    temperature_celsius: float
    timestamp: datetime
    reading_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.device_id:
            raise ValueError("device_id must not be empty")
        if not -100.0 <= self.temperature_celsius <= 100.0:
            raise ValueError(
                f"temperature_celsius must be between -100 and 100, got {self.temperature_celsius}"
            )
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

    def is_out_of_range(self, thresholds: TemperatureThresholds) -> bool:
        """Return True if the reading falls outside the given thresholds."""
        return thresholds.is_out_of_range(self.temperature_celsius)
