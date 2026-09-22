#!/bin/sh
set -e

# Render assigns the port via the PORT environment variable.
# Docker does not expand ${PORT} inside ENV instructions, and EMQX does not
# expand it either when the value comes from its own environment.
# This wrapper resolves the port at runtime, right before EMQX starts.
export EMQX_LISTENERS__WS__DEFAULT__BIND="0.0.0.0:${PORT:-8083}"

# Pass the original CMD arguments to the EMQX entrypoint.
# Without this, EMQX starts without the "foreground" argument and exits immediately.
exec /usr/bin/docker-entrypoint.sh /opt/emqx/bin/emqx foreground