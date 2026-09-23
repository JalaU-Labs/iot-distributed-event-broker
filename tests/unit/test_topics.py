"""Unit tests for the TopicFactory."""

from __future__ import annotations

import pytest

from iot_system.application.topics import TopicFactory


def test_builds_expected_topics() -> None:
    factory = TopicFactory(prefix="iot/sensors", device_id="sensor-001")
    assert factory.temperature() == "iot/sensors/sensor-001/temperature"
    assert factory.alert() == "iot/sensors/sensor-001/alert"
    assert factory.status() == "iot/sensors/sensor-001/status"


def test_trims_trailing_slash_in_prefix() -> None:
    factory = TopicFactory(prefix="iot/sensors/", device_id="sensor-001")
    assert factory.temperature() == "iot/sensors/sensor-001/temperature"


def test_rejects_empty_prefix() -> None:
    with pytest.raises(ValueError, match="prefix"):
        TopicFactory(prefix="   ", device_id="sensor-001")


def test_rejects_empty_device_id() -> None:
    with pytest.raises(ValueError, match="device_id"):
        TopicFactory(prefix="iot/sensors", device_id="")
