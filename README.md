# IoT Distributed Event Platform

Distributed IoT system based on event-driven architecture using MQTT broker, simulated sensor publisher, and central consumer service.

## Objective

Design and implement an IoT system that receives data from multiple distributed devices and processes it centrally, evaluating protocols, QoS levels, and design patterns.

## Architecture

- **MQTT Broker**: EMQX deployed locally with Docker and in the cloud with Render.
- **Publisher**: Simulated temperature sensor that publishes events asynchronously.
- **Consumer**: Central service that subscribes to topics and processes events.
- **Infrastructure**: Reproducible via Docker Compose and deployable to Render.

## Project Structure

```
.
├── docker/           # Dockerfiles and broker configuration
├── docs/             # Architecture, sequence diagrams, deployment guides
├── notebooks/        # Experimentation and evidence
├── scripts/          # Entry point scripts
├── src/iot_system/   # Main package (domain, application, infrastructure, presentation)
├── tests/            # Unit and integration tests
├── docker-compose.yml
├── render.yaml       # Render Blueprint for cloud deployment
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
# Start local MQTT broker
make up

# Run publisher
uv run iot-publisher

# Run consumer
uv run iot-consumer
```

## Deployment to Render

See [docs/deployment-render.md](docs/deployment-render.md) for detailed instructions.

The `render.yaml` file defines a free web service that runs the EMQX broker with MQTT over WebSockets. The broker is accessible at `wss://<service-name>.onrender.com/mqtt`.

## License

MIT