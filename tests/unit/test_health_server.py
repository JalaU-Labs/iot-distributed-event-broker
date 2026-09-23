"""Unit tests for the minimal HTTP health server."""

from __future__ import annotations

import asyncio

from iot_system.infrastructure.health_server import HealthServer


async def _http_get(host: str, port: int, path: str) -> bytes:
    """Send a minimal HTTP/1.1 GET and return the raw response bytes."""
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
        await writer.drain()
        return await reader.read()
    finally:
        writer.close()
        await writer.wait_closed()


async def test_health_endpoint_returns_200() -> None:
    server = HealthServer(host="127.0.0.1", port=0)
    await server.start()
    try:
        response = await _http_get("127.0.0.1", server.port, "/health")
        assert b"HTTP/1.1 200 OK" in response
        assert response.endswith(b"OK")
    finally:
        await server.stop()


async def test_unknown_path_returns_404() -> None:
    server = HealthServer(host="127.0.0.1", port=0)
    await server.start()
    try:
        response = await _http_get("127.0.0.1", server.port, "/other")
        assert b"HTTP/1.1 404 Not Found" in response
    finally:
        await server.stop()


async def test_stop_is_idempotent() -> None:
    server = HealthServer(host="127.0.0.1", port=0)
    await server.stop()  # not started
    await server.start()
    await server.stop()
    await server.stop()  # second call must not raise


async def test_start_is_idempotent() -> None:
    server = HealthServer(host="127.0.0.1", port=0)
    await server.start()
    port_first = server.port
    await server.start()  # no-op
    assert server.port == port_first
    await server.stop()


async def test_port_property_raises_when_not_running() -> None:
    server = HealthServer(host="127.0.0.1", port=0)
    try:
        _ = server.port
        raise AssertionError("Expected RuntimeError")
    except RuntimeError:
        pass
