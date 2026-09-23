"""Minimal HTTP health server for PaaS deployments.

Render, Railway, and Fly.io require web services to expose an HTTP port.
For a pure event publisher there is no HTTP API to serve, so this module
provides a tiny asyncio-based server that answers ``GET /health`` with
``200 OK`` and ``404`` for any other path.

No third-party dependency is used: ``asyncio.start_server`` is enough for
a single endpoint and keeps the image small.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from iot_system.infrastructure.logging import get_logger

logger = get_logger(__name__)

_OK_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: text/plain\r\n"
    b"Content-Length: 2\r\n"
    b"Connection: close\r\n"
    b"\r\n"
    b"OK"
)

_NOT_FOUND_RESPONSE = (
    b"HTTP/1.1 404 Not Found\r\n"
    b"Content-Type: text/plain\r\n"
    b"Content-Length: 9\r\n"
    b"Connection: close\r\n"
    b"\r\n"
    b"Not Found"
)


class HealthServer:
    """Async HTTP server that answers ``GET /health``.

    Binds to ``host:port`` and serves a single health endpoint. Any other
    path or method receives ``404``. The server uses HTTP/1.1 with
    ``Connection: close`` on every response for simplicity.
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._server: asyncio.Server | None = None

    @property
    def port(self) -> int:
        """Return the actual bound port. Useful when ``port=0`` was requested."""
        if self._server is None or not self._server.sockets:
            raise RuntimeError("Health server is not running")
        address = self._server.sockets[0].getsockname()
        return int(address[1])

    async def start(self) -> None:
        """Start listening. Idempotent."""
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self._host,
            port=self._port,
        )
        logger.info(
            "health_server.started",
            host=self._host,
            port=self.port,
        )

    async def stop(self) -> None:
        """Stop listening. Idempotent."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        logger.info("health_server.stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        with suppress(Exception):
            await self._serve_request(reader, writer)
        with suppress(Exception):
            writer.close()
            await writer.wait_closed()

    async def _serve_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        request_line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            if line in (b"\r\n", b"\n", b""):
                break

        is_health = request_line.startswith(b"GET /health ")
        response = _OK_RESPONSE if is_health else _NOT_FOUND_RESPONSE
        writer.write(response)
        await writer.drain()
