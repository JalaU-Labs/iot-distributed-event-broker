#!/bin/sh
set -e

# Internal port where EMQX listens for WebSocket connections.
INTERNAL_WS_PORT=8083

# Render assigns the public-facing port via the PORT environment variable.
RENDER_PORT="${PORT:-8083}"
export PORT="${RENDER_PORT}"

# Render the EMQX configuration with the internal WS port.
sed "s/__MQTT_WS_PORT__/${INTERNAL_WS_PORT}/g" \
    /opt/emqx/etc/emqx.render.conf.template \
    > /opt/emqx/etc/emqx.conf

# Start EMQX in the background.
/usr/bin/docker-entrypoint.sh /opt/emqx/bin/emqx foreground &
EMQX_PID=$!

# Ensure EMQX is terminated when this script exits.
trap 'kill ${EMQX_PID} 2>/dev/null || true' EXIT

# Wait for the internal WebSocket port to be open.
echo "Waiting for EMQX to start (port ${INTERNAL_WS_PORT})..."
for i in $(seq 1 30); do
    if nc -z localhost "${INTERNAL_WS_PORT}"; then
        echo "EMQX is ready."
        break
    fi
    sleep 1
done

# Start Caddy in the foreground as the main process.
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile