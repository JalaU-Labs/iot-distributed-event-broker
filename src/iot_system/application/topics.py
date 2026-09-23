"""MQTT topic construction for a device.

Centralizing topic construction here prevents string duplication and
guarantees a consistent topic hierarchy across the system.
"""

from __future__ import annotations


class TopicFactory:
    """Builds MQTT topics scoped to a single device.

    The naming convention is:

    ``<prefix>/<device_id>/<channel>``

    where channel is one of ``temperature``, ``alert`` or ``status``.
    """

    def __init__(self, prefix: str, device_id: str) -> None:
        if not prefix.strip():
            raise ValueError("topic prefix must not be empty")
        if not device_id.strip():
            raise ValueError("device_id must not be empty")
        self._prefix = prefix.strip().rstrip("/")
        self._device_id = device_id.strip()

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def prefix(self) -> str:
        return self._prefix

    def temperature(self) -> str:
        """Topic for normal temperature readings."""
        return f"{self._prefix}/{self._device_id}/temperature"

    def alert(self) -> str:
        """Topic for out-of-range temperature alerts."""
        return f"{self._prefix}/{self._device_id}/alert"

    def status(self) -> str:
        """Topic for device status updates (retained)."""
        return f"{self._prefix}/{self._device_id}/status"
