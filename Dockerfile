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
# xvfb provides a virtual X display so Playwright can run headed Chromium inside Docker
RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 xvfb && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring in the pre-built venv from the builder
COPY --from=builder /app/.venv /app/.venv

# Install Playwright's bundled Chromium and its system dependencies.
# channel="chrome" (used locally) requires system Chrome which is not in the image;
# in Docker we use bundled Chromium instead. PLAYWRIGHT_BROWSERS_PATH keeps the
# binary out of /root/.cache so it survives layer caching predictably.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN /app/.venv/bin/playwright install --with-deps chromium

# Copy application source
COPY app/ ./app/
COPY config.yaml ./

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# data/ is intentionally excluded from the image and mounted at runtime.
# This keeps the image small and lets datasets persist across rebuilds.
VOLUME ["/app/data"]

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
