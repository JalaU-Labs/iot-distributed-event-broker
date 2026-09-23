"""Validate the AsyncAPI specification against the official JSON schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC_PATH = _REPO_ROOT / "asyncapi.yaml"
_SCHEMA_PATH = _REPO_ROOT / "tests" / "schemas" / "asyncapi-3.0.0.json"


def test_asyncapi_spec_is_valid() -> None:
    spec = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=spec, schema=schema)


def test_asyncapi_declares_all_publish_channels() -> None:
    spec = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))
    channels = spec["channels"]

    assert "temperature" in channels
    assert "alert" in channels
    assert "status" in channels
    assert channels["temperature"]["address"] == "iot/sensors/{deviceId}/temperature"
    assert channels["alert"]["address"] == "iot/sensors/{deviceId}/alert"
    assert channels["status"]["address"] == "iot/sensors/{deviceId}/status"


def test_asyncapi_declares_both_servers() -> None:
    spec = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))
    servers = spec["servers"]

    assert servers["localBroker"]["protocol"] == "mqtt"
    assert servers["localBroker"]["host"] == "localhost:1883"
    assert servers["renderBroker"]["protocol"] == "mqtt"
    assert servers["renderBroker"]["host"] == "iot-emqx-broker.onrender.com:443"


def test_asyncapi_schemas_match_domain_contract() -> None:
    """The SensorReading schema must mirror the domain entity fields."""
    spec = yaml.safe_load(_SPEC_PATH.read_text(encoding="utf-8"))
    schema = spec["components"]["schemas"]["SensorReading"]

    assert set(schema["required"]) == {
        "reading_id",
        "device_id",
        "temperature_celsius",
        "timestamp",
    }
    assert schema["properties"]["temperature_celsius"]["minimum"] == -100
    assert schema["properties"]["temperature_celsius"]["maximum"] == 100
