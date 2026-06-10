# Alerter service — Telegram outbound-only (sendMessage + sendAudio)
# No GPU, no ffmpeg. Just Python + httpx.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ca-certificates for HTTPS calls to api.telegram.org
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY pyproject.toml README.md ./
COPY shared/ ./shared/
COPY alerter/ ./alerter/
COPY config/ ./config/

# httpx is in pyproject extras; alerter is light, no extras required
RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

# Healthcheck: import-only — token optional until WP-6 (dry-run mode)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import alerter; from shared.config import load_telegram_settings; load_telegram_settings()" || exit 1

# Entrypoint: alerter package
CMD ["python", "-m", "alerter"]
