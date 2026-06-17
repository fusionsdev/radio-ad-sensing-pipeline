# Watchdog service — station health loop, auto-restart, Telegram ops alerts
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared/ ./shared/
COPY watchdog/ ./watchdog/
COPY config/ ./config/

RUN pip install --upgrade pip \
    && pip install -e .

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import watchdog; from shared.config import load_settings; load_settings()" || exit 1

CMD ["python", "-m", "watchdog"]
