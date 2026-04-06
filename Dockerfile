# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency manifests first to cache the install layer
COPY pyproject.toml uv.lock ./

# Install production deps into /app/.venv; no dev extras
RUN uv sync --frozen --no-dev

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# curl is used by download_datasets() to fetch IMDB dumps
# libgomp1 is required by LightGBM (OpenMP runtime)
RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring in the pre-built venv from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY app/ ./app/
COPY config.yaml ./

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# data/ is intentionally excluded from the image and mounted at runtime.
# This keeps the image small and lets datasets persist across rebuilds.
VOLUME ["/app/data"]

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
