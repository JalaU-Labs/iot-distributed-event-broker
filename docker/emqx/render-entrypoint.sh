#!/bin/sh
set -e

# Render assigns the WebSocket port dynamically via the PORT environment variable.
# Docker does not expand variables inside ENV instructions, so we render the
# configuration template at container start, before EMQX is launched.
MQTT_WS_PORT="${PORT:-8083}"
sed "s/__MQTT_WS_PORT__/${MQTT_WS_PORT}/g" \
    /opt/emqx/etc/emqx.render.conf.template \
    > /opt/emqx/etc/emqx.conf

exec /usr/bin/docker-entrypoint.sh /opt/emqx/bin/emqx foreground