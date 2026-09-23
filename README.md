# IoT Distributed Event Platform

[![CI](https://github.com/JalaU-Labs/iot-distributed-event-broker/actions/workflows/ci.yml/badge.svg)](https://github.com/JalaU-Labs/iot-distributed-event-broker/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://jalau-labs.github.io/iot-distributed-event-broker/)
[![Event API](https://img.shields.io/badge/event%20API-AsyncAPI%203.0-orange)](https://jalau-labs.github.io/iot-distributed-event-broker/api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Distributed IoT system based on event-driven architecture using an MQTT broker, a simulated sensor publisher, and a central consumer service.

## Objective

Design and implement an IoT system that receives data from multiple distributed devices and processes it centrally, evaluating protocols, QoS levels, and design patterns.

## Architecture

- **MQTT Broker** — EMQX 5.8 deployed locally with Docker and in the cloud with Render (WebSocket over TLS).
- **Publisher** — simulated temperature sensor that publishes events asynchronously with differentiated QoS levels.
- **Consumer** — central service that subscribes to topics, decodes readings, and logs a structured summary.
- **Demo publisher** — low-frequency publisher deployed on Render that keeps the free-tier broker awake and provides a public live stream.
- **Infrastructure** — reproducible locally via Docker Compose; deployed to Render via Blueprint.

See [`docs/architecture.md`](docs/architecture.md) for the C4 diagrams and [`docs/sequence.md`](docs/sequence.md) for the MQTT flow diagrams.

## Public Resources

The project is deployed and documented publicly:

| Resource                   | URL                                                            |
|----------------------------|----------------------------------------------------------------|
| Documentation landing page | https://jalau-labs.github.io/iot-distributed-event-broker/     |
| AsyncAPI reference (HTML)  | https://jalau-labs.github.io/iot-distributed-event-broker/api/ |
| Broker WebSocket endpoint  | `wss://iot-emqx-broker.onrender.com/mqtt`                      |
| Demo publisher health      | https://iot-demo-publisher.onrender.com/health                 |

The broker runs on Render's free tier under a best-effort policy: no SLA, no authentication, no persistence. See [`docs/deployment-render.md`](docs/deployment-render.md) for limitations.

## Project Structure

```
.
├── asyncapi.yaml               # AsyncAPI 3.0 specification of the event API
├── docker/
│   ├── app/                    # Production image for the Python application
│   └── emqx/                   # EMQX configs, Caddyfile, entrypoints
├── docs/                       # Architecture, sequence, deployment, and API guides
│   └── pages/                  # Static landing page published to GitHub Pages
├── notebooks/                  # Experimentation and evidence
├── src/iot_system/
│   ├── domain/                 # Entities and protocols
│   ├── application/            # Publisher, consumer, topic factory
│   ├── infrastructure/         # Config, logging, cache, weather, MQTT, serialization, health server
│   └── presentation/           # CLI entry points and composition root
├── tests/
│   ├── schemas/                # Vendored AsyncAPI JSON schema for offline validation
│   ├── unit/                   # Isolated unit tests
│   └── integration/            # Tests against a running broker
├── docker-compose.yml          # Local broker deployment
├── render.yaml                 # Render Blueprint (broker + demo publisher)
├── Makefile
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.14
- uv 0.12+
- Docker 29+
- Docker Compose 5+

## Quick Start (Local)

The full stack runs in Docker. No Python installation is required.

```bash
# Build and start the broker, publisher, and consumer.
make up

# Show the status of every service.
make ps

# Follow the logs of the publisher and the consumer.
make up-logs

# Follow the logs of a single service.
docker compose logs -f consumer

# Open a shell inside a running container.
docker compose exec publisher bash
docker compose exec consumer bash
docker compose exec emqx bash

# Stop the whole stack.
make down
```

| Service     | Purpose                               | Exposed Port                              |
|-------------|---------------------------------------|-------------------------------------------|
| `emqx`      | MQTT broker + dashboard               | 1883 (MQTT), 8083 (WS), 18083 (dashboard) |
| `publisher` | Simulated sensor publishing every 2 s | none                                      |
| `consumer`  | Central event consumer                | none                                      |

The EMQX dashboard is available at **http://localhost:18083** (`admin` / `public`).

### Running only the broker

If you have your own Python toolchain and want to run the publisher and
consumer from the host:

```bash
# Start only the broker.
make up-broker

# Run the consumer from the host in one terminal.
uv run iot-consumer

# Run the publisher from the host in another terminal.
uv run iot-publisher
```

### Customising the stack

Every value in `docker-compose.yml` can be overridden via `.env` or the
shell:

```bash
DEVICE_DEVICE_ID=sensor-042 DEVICE_PUBLISH_INTERVAL_SECONDS=5 docker compose up -d publisher
```

## Entry Points

After `uv sync`, the following console scripts become available:

| Command              | Purpose                                              |
|----------------------|------------------------------------------------------|
| `iot-publisher`      | Simulated sensor publisher                           |
| `iot-consumer`       | Central event consumer                               |
| `iot-demo-publisher` | Low-frequency publisher with HTTP `/health` endpoint |

## Quality Gates

```bash
make check              # format + lint + types + unit tests with coverage
make test-integration   # integration tests against a running broker
make test-all           # all tests without coverage
make pre-commit         # run pre-commit hooks
make asyncapi-validate  # validate the AsyncAPI specification
make asyncapi-docs      # generate HTML documentation for the spec
make pages-build        # build the GitHub Pages site locally
```

## Continuous Integration

Both GitHub Actions and GitLab CI run the same pipeline:

- **Quality:** `ruff format --check`, `ruff check`, `mypy`
- **Unit tests:** `pytest -m "not integration"` with a coverage gate at 60%
- **Integration tests:** spin up an ephemeral EMQX container and run `pytest -m integration`

- GitHub Actions: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- GitLab CI: [`.gitlab-ci.yml`](.gitlab-ci.yml)

## Documentation

### Online

- [Landing page](https://jalau-labs.github.io/iot-distributed-event-broker/)
- [Event API reference (AsyncAPI 3.0)](https://jalau-labs.github.io/iot-distributed-event-broker/api/)

### In the repository

- [Architecture (C4)](docs/architecture.md)
- [Sequence diagrams](docs/sequence.md)
- [AsyncAPI guide](docs/asyncapi.md)
- [Render deployment guide](docs/deployment-render.md)
- [Demo publisher](docs/demo-publisher.md)
- [Evidence notebook](notebooks/01_mqtt_flow_evidence.ipynb)

## Design Principles

- **Layered architecture** with strict dependency direction: `presentation → application → domain ← infrastructure`.
- **SOLID** applied throughout: Dependency Inversion via `Protocol` definitions, Interface Segregation with narrow protocols, Single Responsibility per module.
- **Twelve-Factor App** configuration: all settings come from environment variables, validated at startup with `pydantic-settings`.
- **Composition Root** pattern: the only place where concrete adapters are instantiated is `presentation/container.py`.
- **Fail-safe boundaries**: the publisher loop recovers from transient errors; the CLI translates connection failures into user-facing messages with a non-zero exit code.

## License

MIT