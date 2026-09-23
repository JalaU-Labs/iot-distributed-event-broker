"""Structured logging configuration using structlog.

Supports both human-readable (dev) and JSON (prod) outputs. The logger is
configured once at process startup and reused across the application.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from iot_system.infrastructure.config import LoggingConfig


def _add_severity(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Copy the log level into a top-level `severity` field for JSON consumers."""
    event_dict["severity"] = event_dict.get("level", "info").upper()
    return event_dict


def configure_logging(config: LoggingConfig) -> None:
    """Configure structlog and the stdlib logging bridge.

    This function is idempotent: calling it twice simply re-applies the
    configuration. It should be invoked exactly once at process startup.
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_severity,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if config.json_format:
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(config.level)),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=logging.getLevelName(config.level),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound logger with the given name."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
