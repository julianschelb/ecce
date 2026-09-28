# ECCE backend (API only). For the single-image full-stack build see ../Dockerfile.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 UV_SYSTEM_PYTHON=1
WORKDIR /app

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
COPY pyproject.toml README.md ./
COPY app ./app
# CPU-only torch wheels are not needed: the default extractor is spaCy (small, CPU).
RUN uv pip install --no-cache ".[spacy]"

FROM base AS runtime
RUN useradd --create-home --uid 1000 ecce
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=ecce:ecce app ./app
COPY --chown=ecce:ecce data/seed ./seed
COPY --chown=ecce:ecce scripts ./scripts
RUN mkdir -p /app/data && chown -R ecce:ecce /app/data
USER ecce
ENV PORT=8000 DATA_DIR=/app/data SEED_DIR=/app/seed SEED_ASYNC=true EXTRACTOR=auto
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
