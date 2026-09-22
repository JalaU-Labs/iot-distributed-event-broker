#!/bin/sh
set -e

INTERNAL_WS_PORT=8083

if [ -z "${PORT}" ]; then
    echo "ERROR: PORT environment variable is not set. Render must provide it."
    exit 1
fi

echo "Using Render-assigned port: ${PORT}"

sed "s/__MQTT_WS_PORT__/${INTERNAL_WS_PORT}/g" \
    /opt/emqx/etc/emqx.render.conf.template \
    > /opt/emqx/etc/emqx.conf

/usr/bin/docker-entrypoint.sh /opt/emqx/bin/emqx foreground &
EMQX_PID=$!

trap 'kill ${EMQX_PID} 2>/dev/null || true' EXIT

echo "Waiting for EMQX to start (port ${INTERNAL_WS_PORT})..."
for i in $(seq 1 60); do
    if nc -z 127.0.0.1 "${INTERNAL_WS_PORT}"; then
        echo "EMQX is ready."
        break
    fi
    sleep 1
done

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile