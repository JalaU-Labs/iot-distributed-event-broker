# Architecture

This document describes the IoT Distributed Event Platform using C4-style diagrams (Context and Container levels) and complementary diagrams. All diagrams use Mermaid syntax and render natively on GitHub and GitLab.

## System Context

```mermaid
C4Context
    title System Context - IoT Distributed Event Platform

    Person(operator, "Lab Operator", "Runs the publisher and consumer and observes the broker.")

    System(platform, "IoT Event Platform", "Publishes simulated sensor readings and consumes them centrally.")

    System_Ext(openmeteo, "Open-Meteo API", "Public weather service that provides current temperature by coordinates.")
    System_Ext(render, "Render", "Free-tier cloud host that runs the MQTT broker over WebSockets.")
    System_Ext(docker, "Docker Engine", "Runs the local EMQX broker for development.")

    Rel(operator, platform, "Runs and monitors", "CLI")
    Rel(platform, openmeteo, "Fetches temperature", "HTTPS / JSON")
    Rel(platform, docker, "Uses for local broker", "Docker Compose")
    Rel(platform, render, "Uses for cloud broker", "MQTT over WSS")
```

## Container View

```mermaid
C4Container
    title Container View - IoT Distributed Event Platform

    Person(operator, "Lab Operator")

    Container_Boundary(platform, "IoT Event Platform") {
        Container(publisher, "Sensor Publisher", "Python 3.14 / aiomqtt", "Fetches temperature, adds noise, and publishes readings with differentiated QoS.")
        Container(consumer, "Event Consumer", "Python 3.14 / aiomqtt", "Subscribes to temperature and alert topics, decodes readings, and logs a summary.")
        Container(shared, "Shared Libraries", "Python 3.14", "Domain entities, protocols, infrastructure adapters, and the composition root.")
    }

    Container_Boundary(broker_local, "Local Broker") {
        Container(emqx_local, "EMQX", "Docker image emqx/emqx:5.8.0", "MQTT broker reachable on tcp://localhost:1883.")
    }

    Container_Boundary(broker_cloud, "Cloud Broker") {
        Container(caddy, "Caddy", "Reverse proxy", "Serves /health and reverse-proxies /mqtt to EMQX.")
        Container(emqx_cloud, "EMQX", "Docker image emqx/emqx:5.8.0", "MQTT broker bound to 127.0.0.1:8083, fronted by Caddy.")
    }

    System_Ext(openmeteo, "Open-Meteo API")

    Rel(operator, publisher, "Starts", "CLI / iot-publisher")
    Rel(operator, consumer, "Starts", "CLI / iot-consumer")
    Rel(publisher, openmeteo, "Fetches temperature", "HTTPS")
    Rel(publisher, emqx_local, "Publishes readings", "MQTT / TCP 1883")
    Rel(consumer, emqx_local, "Subscribes to topics", "MQTT / TCP 1883")
    Rel(publisher, caddy, "Publishes readings", "MQTT over WSS")
    Rel(consumer, caddy, "Subscribes to topics", "MQTT over WSS")
    Rel(caddy, emqx_cloud, "Reverse proxies", "HTTP/WebSocket")
```

## Layered Structure

```mermaid
flowchart TB
    subgraph Presentation["Presentation Layer"]
        CLI[cli.py]
        Container[container.py]
    end

    subgraph Application["Application Layer"]
        Publisher[SensorPublisher]
        Consumer[SensorConsumer]
        Topics[TopicFactory]
    end

    subgraph Domain["Domain Layer"]
        Entities[entities.py]
        Protocols[interfaces.py]
    end

    subgraph Infrastructure["Infrastructure Layer"]
        Config[config.py]
        Logging[logging.py]
        Clock[clock.py]
        Cache[cache.py]
        Weather[weather.py]
        MQTT[mqtt.py]
        Serialization[serialization.py]
    end

    CLI --> Container
    Container --> Publisher
    Container --> Consumer
    Publisher --> Topics
    Publisher --> Entities
    Publisher --> Protocols
    Consumer --> Entities
    Consumer --> Protocols
    Infrastructure -.implements.-> Protocols
```

## Design Principles

- **Dependency Inversion:** The domain and application layers depend only on `Protocol` definitions; the infrastructure layer provides concrete implementations.
- **Interface Segregation:** Protocols expose the minimum contract required by each consumer (`RandomProtocol` exposes only `uniform`, `MQTTSubscriberProtocol` only `subscribe` and `messages`).
- **Single Responsibility:** Each module addresses one concern (cache, weather, MQTT, serialization, configuration, logging).
- **Composition Root:** `presentation/container.py` is the only place where concrete adapters are instantiated and bound to use cases.
- **Twelve-Factor App:** All configuration is provided via environment variables, validated at startup with `pydantic-settings`.