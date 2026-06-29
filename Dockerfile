# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:///./data/classifier.db \
    ENABLE_PD_CLEANING=true \
    ENABLE_PD_CLEANING_LOG=true \
    ENABLE_CLASSIFICATION_LOGGING=true \
    PD_MODEL_VERSION=pd-cpu-v1 \
    LOG_LEVEL=INFO \
    PORT=8123

WORKDIR /app

RUN groupadd -r classifier && useradd -r -g classifier classifier

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app ./app
COPY data ./data
COPY scripts/docker-entrypoint.sh ./scripts/docker-entrypoint.sh

RUN mkdir -p /app/data/training \
    && chmod +x /app/scripts/docker-entrypoint.sh \
    && chown -R classifier:classifier /app

USER classifier

EXPOSE 8123

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",\"8123\")}/health', timeout=2)"

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]