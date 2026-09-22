# Deploying the MQTT Broker to Render

This guide explains how to deploy the EMQX MQTT broker to Render using the free plan and WebSocket transport.

## Prerequisites

- A Render account (free tier is sufficient).
- A GitHub or GitLab repository containing this project.
- The repository must be connected to Render.

## Why WebSockets Instead of TCP?

Render's free plan does not expose arbitrary TCP ports. The standard MQTT port 1883 is therefore unreachable from outside Render's network. The only way to expose MQTT is through WebSockets, which Render supports on the HTTP/HTTPS port (443).

This means:

- The broker listens on a dynamic port assigned by Render via the `PORT` environment variable.
- Clients must connect using `wss://<service-name>.onrender.com/mqtt` (TLS is terminated by Render).
- The TCP listener (1883) and the dashboard (18083) are disabled in production.

## Deployment Steps

### 1. Connect the Repository

1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New** > **Blueprint**.
3. Connect your GitHub or GitLab account and select the repository.
4. Render will detect the `render.yaml` file at the root.

### 2. Review the Blueprint

Render will show a preview of the service defined in `render.yaml`:

- **Name**: `iot-emqx-broker`
- **Type**: Web Service
- **Runtime**: Docker
- **Plan**: Free
- **Region**: `oregon` (change if needed)

### 3. Deploy

Click **Apply**. Render will:

1. Build the Docker image from `docker/emqx/Dockerfile.render`.
2. Start the container with the environment variables defined in `render.yaml`.
3. Assign a public HTTPS URL, e.g. `https://iot-emqx-broker.onrender.com`.

### 4. Verify the Deployment

Once the service is live:

- **MQTT WebSocket endpoint**: `wss://iot-emqx-broker.onrender.com/mqtt`
- **Port detection**: Render scans the container for HTTP services. The wrapper
  script binds the EMQX WebSocket listener to the port assigned by Render via
  the `PORT` environment variable, so Render will detect it automatically.
- **No health check**: The blueprint does not declare a `healthCheckPath`.
  Render will consider the service healthy as soon as the container starts.

### 5. Connect a Client

From your local machine, configure the publisher and consumer to use:

```
MQTT_BROKER_HOST=iot-emqx-broker.onrender.com
MQTT_BROKER_PORT=443
MQTT_TRANSPORT=websockets
MQTT_USE_TLS=true
MQTT_WS_PATH=/mqtt
```

These variables are read by the application (see `.env.example`).

## Free Plan Limitations

- **No persistent disk**: All messages and sessions are lost when the service restarts.
- **Spin-down**: The service sleeps after 15 minutes without inbound traffic. While the publisher is active (publishing every 2 seconds), the service stays awake. When the publisher stops, the service sleeps and the consumer must reconnect.
- **Cold start**: After sleeping, the first connection takes ~30 seconds to wake the service.

## Troubleshooting

### Service fails to start

Check the logs in the Render dashboard. Common causes:

- Port binding conflict: ensure `EMQX_LISTENERS__WS__DEFAULT__BIND` is set to `0.0.0.0:${PORT}`.
- Invalid environment variable format: EMQX uses double underscores (`__`) for nested config keys.

### Client cannot connect

- Verify the URL uses `wss://` (not `ws://`).
- Verify the path is `/mqtt`.
- Check that `MQTT_TRANSPORT=websockets` is set in the client.
- Ensure the service is awake (visit the Render dashboard or make an HTTP request).

### Port detection fails

If Render reports "No open HTTP ports detected", verify in the logs that the
WebSocket listener bound to the port assigned by Render (e.g. `Listener ws:default on 0.0.0.0:10000 started.`).
If it bound to `8083` instead, the wrapper script is not being executed. Check
that the Dockerfile's `ENTRYPOINT` points to `/usr/local/bin/render-entrypoint.sh`.

## References

- [Render Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Render Free Plan Limitations](https://render.com/docs/free)
- [EMQX Configuration via Environment Variables](https://www.emqx.io/docs/en/v5.8/configuration/configuration.html)
