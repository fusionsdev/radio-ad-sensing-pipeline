# Dashboard service — FastAPI + Jinja2/HTMX, read-only over SQLite
# No GPU, no ffmpeg. LAN-only by default (binds to 127.0.0.1 in compose).
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# curl for HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY pyproject.toml README.md ./
COPY shared/ ./shared/
COPY dashboard/ ./dashboard/
COPY config/ ./config/

# FastAPI + uvicorn + jinja2 from the dashboard extras
RUN pip install --upgrade pip \
    && pip install -e ".[dashboard]"

# Default port from settings.yaml (8080); overridden in compose if needed
EXPOSE 8080

# Healthcheck hits the /health endpoint after uvicorn is up
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

# Entrypoint: dashboard package
CMD ["python", "-m", "dashboard"]
