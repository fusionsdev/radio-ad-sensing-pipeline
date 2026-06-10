# Worker service — faster-whisper ASR + (later) Ollama extraction + dedup
# Requires NVIDIA GPU access at runtime (configured in docker-compose).
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: ffmpeg for audio probing, libsndfile for some audio paths, build tools
# for faster-whisper's ctranslate2 dependency (kept minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching
COPY pyproject.toml README.md ./
COPY shared/ ./shared/
COPY collectors/ ./collectors/
COPY worker/ ./worker/
COPY config/ ./config/

# faster-whisper pulls ctranslate2 + tokenizers; both need wheel builds.
# ctranslate2 GPU needs NVIDIA CUDA libs — not bundled in python:3.11-slim.
RUN pip install --upgrade pip \
    && pip install -e ".[worker]" \
    && pip install nvidia-cublas-cu12 nvidia-cuda-nvrtc-cu12

# ctranslate2 loads libcublas from the nvidia-* pip wheels at runtime.
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_nvrtc/lib

# GPU sanity check: nvidia-smi must be present in the container
# (provided by the NVIDIA container runtime at /usr/local/nvidia/bin)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import faster_whisper; print('ok')" || exit 1

# Entrypoint: worker package
CMD ["python", "-m", "worker", "data/pipeline.db"]
