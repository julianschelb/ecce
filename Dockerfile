# Full-stack image (used by Railway): builds the React app and serves it from FastAPI.
# --------------------------------------------------------------------------- frontend
FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# --------------------------------------------------------------------------- backend deps
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 UV_SYSTEM_PYTHON=1
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app
RUN uv pip install --no-cache ".[spacy]"

# --------------------------------------------------------------------------- runtime
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 1000 ecce
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=ecce:ecce backend/app ./app
COPY --chown=ecce:ecce backend/data/seed ./seed
COPY --chown=ecce:ecce backend/scripts ./scripts
COPY --from=frontend --chown=ecce:ecce /web/dist ./static
RUN mkdir -p /app/data && chown -R ecce:ecce /app/data
USER ecce
ENV PORT=8000 DATA_DIR=/app/data SEED_DIR=/app/seed SEED_ASYNC=true FRONTEND_DIST=/app/static EXTRACTOR=auto
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
