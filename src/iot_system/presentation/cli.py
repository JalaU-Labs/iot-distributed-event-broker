"""Command-line entry points for the IoT platform.

Exposes two commands, ``publisher`` and ``consumer``, both built on Typer.
The functions ``run_publisher`` and ``run_consumer`` are declared as
entry points in ``pyproject.toml`` so that ``iot-publisher`` and
``iot-consumer`` become available as console scripts after installation.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Annotated

import typer

from iot_system.application.consumer import SensorConsumer
from iot_system.application.publisher import SensorPublisher
from iot_system.infrastructure.config import Settings, get_settings
from iot_system.infrastructure.health_server import HealthServer
from iot_system.infrastructure.logging import configure_logging, get_logger
from iot_system.infrastructure.mqtt import MQTTConnectionError
from iot_system.infrastructure.wakeup import BrokerWakeUpWaiter
from iot_system.presentation.container import Container

logger = get_logger(__name__)

publisher_app = typer.Typer(
    name="iot-publisher",
    help="Run the simulated IoT sensor publisher.",
    add_completion=False,
    no_args_is_help=False,
)
consumer_app = typer.Typer(
    name="iot-consumer",
    help="Run the central event consumer.",
    add_completion=False,
    no_args_is_help=False,
)
demo_publisher_app = typer.Typer(
    name="iot-demo-publisher",
    help="Run a low-frequency publisher that keeps a cloud broker awake.",
    add_completion=False,
    no_args_is_help=False,
)


async def _run_with_signals(
    run: Awaitable[None],
    stop_event: asyncio.Event,
) -> None:
    """Run ``run`` until it completes or a termination signal is received.

    Registers handlers for SIGINT and SIGTERM that set ``stop_event``.
    On platforms where ``add_signal_handler`` is unavailable (Windows),
    the KeyboardInterrupt propagates and terminates the process.
    """
    loop = asyncio.get_running_loop()

    def _handle_signal() -> None:
        logger.info("cli.shutdown_signal_received")
        stop_event.set()

    registered = False
    with suppress(NotImplementedError):
        loop.add_signal_handler(signal.SIGINT, _handle_signal)
        loop.add_signal_handler(signal.SIGTERM, _handle_signal)
        registered = True

    try:
        await run
    finally:
        if registered:
            with suppress(NotImplementedError):
                loop.remove_signal_handler(signal.SIGINT)
                loop.remove_signal_handler(signal.SIGTERM)


def _execute(
    coro_factory: Callable[[asyncio.Event], Awaitable[None]],
    settings: Settings,
) -> None:
    """Run an asyncio coroutine factory, handling Ctrl+C and broker errors."""

    async def _runner() -> None:
        stop_event = asyncio.Event()
        async with BrokerWakeUpWaiter(settings.wakeup) as waiter:
            if not await waiter.wait_until_ready():
                logger.error(
                    "cli.wakeup_timeout",
                    url=settings.wakeup.url,
                    timeout_seconds=settings.wakeup.timeout_seconds,
                    hint=(
                        "The demo publisher did not respond. "
                        "Check https://iot-demo-publisher.onrender.com/health "
                        "in your browser or disable WAKEUP_ENABLED."
                    ),
                )
                sys.exit(1)
        await _run_with_signals(coro_factory(stop_event), stop_event)

    try:
        asyncio.run(_runner())
    except KeyboardInterrupt:
        sys.exit(130)
    except MQTTConnectionError as exc:
        logger.error(
            "cli.connection_failed",
            error=str(exc),
            hint=(
                "Ensure the MQTT broker is reachable. "
                "Start the local broker with 'make up', or set "
                "MQTT_BROKER_HOST/PORT/TRANSPORT/USE_TLS/WS_PATH in .env "
                "for a cloud deployment."
            ),
        )
        sys.exit(1)


@publisher_app.callback(invoke_without_command=True)
def run_publisher(
    device_id: Annotated[
        str | None,
        typer.Option(help="Override the device identifier."),
    ] = None,
) -> None:
    """Run the simulated sensor publisher until interrupted."""
    settings = get_settings()
    if device_id is not None:
        settings = settings.model_copy(
            update={
                "device": settings.device.model_copy(update={"device_id": device_id}),
            }
        )
    configure_logging(settings.logging)
    logger.info(
        "cli.publisher_starting",
        device_id=settings.device.device_id,
        broker=settings.mqtt.broker_host,
        transport=settings.mqtt.transport,
    )
    publisher: SensorPublisher = Container(settings).build_publisher()
    _execute(lambda stop_event: publisher.run_forever(stop_event), settings)


@consumer_app.callback(invoke_without_command=True)
def run_consumer() -> None:
    """Run the central event consumer until interrupted."""
    settings = get_settings()
    configure_logging(settings.logging)
    logger.info(
        "cli.consumer_starting",
        broker=settings.mqtt.broker_host,
        transport=settings.mqtt.transport,
        topic_prefix=settings.mqtt.topic_prefix,
    )
    consumer: SensorConsumer = Container(settings).build_consumer()
    _execute(lambda stop_event: consumer.run_forever(stop_event), settings)


@demo_publisher_app.callback(invoke_without_command=True)
def run_demo_publisher() -> None:
    """Run the low-frequency publisher until interrupted.

    This variant serves an HTTP ``/health`` endpoint on the port assigned
    by the PaaS provider, so the service qualifies as a Render web service.
    The publisher itself is the same ``SensorPublisher`` used elsewhere;
    only the operational envelope differs.
    """
    settings = get_settings()
    configure_logging(settings.logging)
    port = int(os.environ.get("PORT", "8080"))
    logger.info(
        "cli.demo_publisher_starting",
        broker=settings.mqtt.broker_host,
        transport=settings.mqtt.transport,
        interval_seconds=settings.device.publish_interval_seconds,
        health_port=port,
    )
    publisher: SensorPublisher = Container(settings).build_publisher()

    async def _run(stop_event: asyncio.Event) -> None:
        health = HealthServer(host="0.0.0.0", port=port)
        await health.start()
        try:
            await publisher.run_forever(stop_event)
        finally:
            await health.stop()

    _execute(_run, settings)


# Root CLI that groups both commands for ad-hoc usage: `python -m ... publisher`.
root_app = typer.Typer(
    name="iot-platform",
    help="IoT Distributed Event Platform.",
    add_completion=False,
    no_args_is_help=True,
)
root_app.add_typer(publisher_app, name="publisher")
root_app.add_typer(consumer_app, name="consumer")
root_app.add_typer(demo_publisher_app, name="demo-publisher")


if __name__ == "__main__":
    root_app()
