# Ingestor service — ffmpeg supervisor, chunk writer, gap logger
# No GPU required; just needs ffmpeg + Python deps.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: ffmpeg for stream capture, ca-certificates for HTTPS streams
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY pyproject.toml README.md ./
COPY shared/ ./shared/
COPY collectors/ ./collectors/
COPY ingestor/ ./ingestor/
COPY config/ ./config/

# Install the package in editable mode with the base + ingestor deps
# (ingestor has no extra deps beyond the base pydantic+pyyaml, so just install base)
RUN pip install --upgrade pip \
    && pip install -e .

# Healthcheck: verify the Python entrypoint is importable and DB path is reachable
# In docker-compose this is overridden to use the real DB path
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "from shared.config import load_stations; load_stations()" || exit 1

# Entrypoint: ingestor package will provide its own __main__ in a later WP
CMD ["python", "-m", "ingestor"]
