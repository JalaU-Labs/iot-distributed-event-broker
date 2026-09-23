"""Command-line entry points for the IoT platform.

Exposes two commands, ``publisher`` and ``consumer``, both built on Typer.
The functions ``run_publisher`` and ``run_consumer`` are declared as
entry points in ``pyproject.toml`` so that ``iot-publisher`` and
``iot-consumer`` become available as console scripts after installation.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Annotated

import typer

from iot_system.application.consumer import SensorConsumer
from iot_system.application.publisher import SensorPublisher
from iot_system.infrastructure.config import get_settings
from iot_system.infrastructure.logging import configure_logging, get_logger
from iot_system.infrastructure.mqtt import MQTTConnectionError
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
) -> None:
    """Run an asyncio coroutine factory, handling Ctrl+C and broker errors."""

    async def _runner() -> None:
        stop_event = asyncio.Event()
        await _run_with_signals(coro_factory(stop_event), stop_event)

    try:
        asyncio.run(_runner())
    except KeyboardInterrupt:
        # User pressed Ctrl+C; exit code 130 is the convention for SIGINT.
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
    _execute(lambda stop_event: publisher.run_forever(stop_event))


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
    _execute(lambda stop_event: consumer.run_forever(stop_event))


# Root CLI that groups both commands for ad-hoc usage: `python -m ... publisher`.
root_app = typer.Typer(
    name="iot-platform",
    help="IoT Distributed Event Platform.",
    add_completion=False,
    no_args_is_help=True,
)
root_app.add_typer(publisher_app, name="publisher")
root_app.add_typer(consumer_app, name="consumer")


if __name__ == "__main__":
    root_app()
