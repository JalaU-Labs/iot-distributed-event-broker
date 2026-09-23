# IoT Distributed Event Platform

Distributed IoT system based on event-driven architecture using MQTT broker, simulated sensor publisher, and central consumer service.

## Objective

Design and implement an IoT system that receives data from multiple distributed devices and processes it centrally, evaluating protocols, QoS levels, and design patterns.

## Architecture

- **MQTT Broker**: EMQX deployed locally with Docker and in the cloud with Render.
- **Publisher**: Simulated temperature sensor that publishes events asynchronously.
- **Consumer**: Central service that subscribes to topics and processes events.
- **Infrastructure**: Reproducible via Docker Compose and deployable to Render.

See [docs/architecture.md](docs/architecture.md) for the full C4 diagrams, and [docs/sequence.md](docs/sequence.md) for the MQTT flow diagrams.

## Project Structure

```
.
├── docker/                 # Dockerfiles and broker configuration
│   └── emqx/               # EMQX configs, Caddyfile, entrypoints
├── docs/                   # Architecture, sequence diagrams, deployment guides
├── notebooks/              # Experimentation and evidence
├── scripts/                # Ad-hoc scripts
├── src/iot_system/
│   ├── domain/             # Entities and protocols
│   ├── application/        # Publisher, consumer, topic factory
│   ├── infrastructure/     # Config, logging, cache, weather, MQTT, serialization
│   └── presentation/       # CLI and composition root
├── tests/
│   ├── unit/               # Isolated unit tests
│   └── integration/        # Tests against a running broker
├── docker-compose.yml
├── render.yaml
├── Makefile
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.14.6
- uv 0.12.17
- Docker 29.8.1
- Docker Compose 5.5.1

## Quick Start (Local)

```bash
# 1. Start the local MQTT broker
make up

# 2. Run the consumer in one terminal
uv run iot-consumer

# 3. Run the publisher in another terminal
uv run iot-publisher
```

Stop both processes with `Ctrl+C`. Stop the broker with `make down`.

## Quality Gates

```bash
make check              # format + lint + types + unit tests with coverage
make test-integration   # integration tests against a running broker
make pre-commit         # run pre-commit hooks
```

## Continuous Integration

Both repositories run the same pipeline:

- **Quality:** `ruff format --check`, `ruff check`, `mypy`
- **Unit tests:** `pytest -m "not integration"` with coverage gate at 60%
- **Integration tests:** spin up an ephemeral EMQX container and run `pytest -m integration`

- GitHub Actions: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
- GitLab CI: [`.gitlab-ci.yml`](.gitlab-ci.yml)

## Documentation

- [Architecture (C4)](docs/architecture.md)
- [Sequence diagrams](docs/sequence.md)
- [Render deployment guide](docs/deployment-render.md)
- [Demo publisher](docs/demo-publisher.md)
- [Evidence notebook](notebooks/01_mqtt_flow_evidence.ipynb)

## Deployment to Render

See [docs/deployment-render.md](docs/deployment-render.md) for detailed instructions.

## License

MIT