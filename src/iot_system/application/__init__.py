"""Application layer: use cases that orchestrate domain and infrastructure.

The application layer depends on the domain protocols, never on concrete
adapters. This keeps the use cases testable in isolation and lets the
infrastructure layer evolve without touching business rules.
"""

from iot_system.application.consumer import ConsumerStats, SensorConsumer
from iot_system.application.publisher import (
    QOS_ALERT,
    QOS_STATUS,
    QOS_TELEMETRY,
    SensorPublisher,
)
from iot_system.application.topics import TopicFactory

__all__ = [
    "QOS_ALERT",
    "QOS_STATUS",
    "QOS_TELEMETRY",
    "ConsumerStats",
    "SensorConsumer",
    "SensorPublisher",
    "TopicFactory",
]
