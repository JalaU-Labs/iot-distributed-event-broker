FROM python:3.14-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# Install uv from the official image. The binary is a static Go executable,
# so it runs on the slim base without additional dependencies.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install runtime dependencies first so the layer is reused when only
# application code changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the source and install the project itself.
COPY src ./src
RUN uv sync --frozen --no-dev

# Run as a non-root user. The virtual environment is readable by all users
# and PYTHONDONTWRITEBYTECODE avoids runtime writes.
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Render provides PORT. Default to 8080 for local runs.
ENV PORT=8080
EXPOSE 8080

CMD ["/app/.venv/bin/iot-demo-publisher"]