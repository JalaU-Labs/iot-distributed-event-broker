# AsyncAPI Specification

The public event API of the IoT platform is described using
[AsyncAPI 3.0](https://www.asyncapi.com/docs/reference/specification/v3.0.0),
the industry standard for event-driven APIs (the OpenAPI equivalent for
message-based systems).

## Files

- [`asyncapi.yaml`](../asyncapi.yaml) — the specification itself.
- [`tests/unit/test_asyncapi_spec.py`](../tests/unit/test_asyncapi_spec.py) —
  automated validation against the official JSON schema.
- `tests/schemas/asyncapi-3.0.0.json` — vendored copy of the official
  AsyncAPI 3.0 JSON schema, so validation runs offline.

## Validating

```bash
make asyncapi-validate
```

This runs a `jsonschema` validation of the spec against the official
AsyncAPI 3.0 schema, plus a set of structural assertions that the
channels, servers, and message schemas match the domain contract.

## Generating HTML documentation

```bash
make asyncapi-docs
```

This invokes the official AsyncAPI CLI via `npx` and generates a
self-contained HTML site at `docs/api/index.html`. Requires Node.js
(any LTS version) to be available on the path.

## What the specification declares

- **Servers** — `localBroker` (TCP, port 1883) and `renderBroker`
  (WebSocket/TLS, port 443).
- **Channels** — `iot/sensors/{deviceId}/temperature`,
  `iot/sensors/{deviceId}/alert`, and `iot/sensors/{deviceId}/status`.
- **Messages** — `SensorReading` and `DeviceStatus`, both with JSON
  schemas that mirror the domain entities.
- **Operations** — send and receive operations for each channel, with
  documentation of the QoS level and retention policy.

## Relationship to the domain

The JSON schemas in the AsyncAPI spec are the canonical wire contract.
The Python domain entity `SensorReading` in
`src/iot_system/domain/entities.py` and the JSON serializer in
`src/iot_system/infrastructure/serialization.py` must be kept in sync
with the schemas. The test `test_asyncapi_schemas_match_domain_contract`
guards the most important invariants.

## References

- [AsyncAPI 3.0 Specification](https://www.asyncapi.com/docs/reference/specification/v3.0.0)
- [MQTT bindings for AsyncAPI](https://github.com/asyncapi/bindings/tree/master/mqtt)
- [AsyncAPI CLI](https://github.com/asyncapi/cli)