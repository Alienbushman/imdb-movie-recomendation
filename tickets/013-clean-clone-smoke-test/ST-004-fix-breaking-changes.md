---
ticket: "013"
subtask: 4
title: "Fix Breaking Changes"
status: Done
effort: high
component: full_stack
depends_on: ["ST-003"]
files_modified:
  - Dockerfile
  - app/services/scrape.py
files_created: []
---

# SUBTASK 04 — Fix All Breaking Changes

---

## Objective

Fix every breaking change documented in ST-001–ST-003. After this subtask a developer
can clone the repo, run `docker compose up --build`, open `http://localhost:9137`,
paste in their IMDB URL, and have it work end-to-end.

---

## Pre-conditions

Read `decisions.md` in full — it contains both the static-analysis findings and the
actual runtime errors found during ST-001–ST-003.

Both suites must pass before writing code:

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

---

## Fix 1 — Playwright Chrome in Docker (CRITICAL)

**Root cause**: `scrape.py` uses `headless=False` + `channel="chrome"`. Docker images
have no X11 display and no Chrome binary. Even Playwright's bundled Chromium is absent
because the Dockerfile never runs `playwright install`.

**Strategy**: Install Chromium (not full Chrome) into the Docker image via Playwright's
own install mechanism, and use `xvfb-run` to provide a virtual X display so `headless=False`
continues to work (required to bypass IMDB's WAF). Local dev continues to use system Chrome.

### 1a. Update `Dockerfile` — add Chromium + Xvfb to runtime stage

Add the following **after** the existing `apt-get` line in the runtime stage (line 20):

```dockerfile
# Install Chromium and Xvfb for IMDB URL scraping inside Docker.
# Playwright requires a display even in "headed" mode; Xvfb provides a virtual one.
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright's bundled Chromium and its system dependencies.
# Must run after the venv is in place (COPY --from=builder above).
RUN PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    /app/.venv/bin/playwright install --with-deps chromium \
    && rm -rf /ms-playwright/chromium-*/chrome-linux/swiftshader
```

Set the browser path env var so Playwright finds the binary at runtime:

```dockerfile
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

(Replace the existing `ENV` block; add `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`.)

### 1b. Update `scrape.py` — detect Docker and switch browser

Add environment detection and a browser-launch helper near the top of the file,
after the existing constants:

```python
import os
import subprocess
import threading

def _running_in_docker() -> bool:
    """Return True when running inside a Docker container."""
    return os.path.exists("/.dockerenv")
```

Replace the `browser = p.chromium.launch(...)` block inside `fetch_imdb_ratings_csv()`
with a helper that selects the right configuration:

**Before** (lines 241-245 approximately):
```python
        browser = p.chromium.launch(
            headless=False,
            channel="chrome",
            args=_PLAYWRIGHT_ARGS,
        )
```

**After**:
```python
        if _running_in_docker():
            browser = p.chromium.launch(
                headless=False,
                args=_PLAYWRIGHT_ARGS + ["--no-sandbox", "--disable-dev-shm-usage"],
            )
        else:
            browser = p.chromium.launch(
                headless=False,
                channel="chrome",
                args=_PLAYWRIGHT_ARGS,
            )
```

Add Xvfb startup at the top of `fetch_imdb_ratings_csv()`, before the
`with sync_playwright() as p:` block:

```python
    if _running_in_docker():
        _start_xvfb_if_needed()
```

Add the Xvfb helper function (module-level):

```python
_xvfb_proc: subprocess.Popen | None = None
_xvfb_lock = threading.Lock()


def _start_xvfb_if_needed() -> None:
    """Start a virtual X display (:99) if not already running.

    Called only in Docker where no display is available.
    Xvfb must be installed in the Docker image (apt-get install xvfb).
    """
    global _xvfb_proc
    with _xvfb_lock:
        if _xvfb_proc is not None and _xvfb_proc.poll() is None:
            return  # already running
        logger.info("Starting Xvfb virtual display for Playwright")
        _xvfb_proc = subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)  # give Xvfb time to initialise
        os.environ["DISPLAY"] = ":99"
```

### 1c. Verify no regressions from channel change

The `channel="chrome"` path is preserved for local dev (non-Docker). The Docker path
uses bundled Chromium which may be detected by IMDB's WAF.

**If Chromium is blocked by IMDB WAF in Docker** (confirmed by ST-003 logs showing
403/blocked responses), fall back to Option 2: surface a clean error and direct the
user to CSV upload. Add this to the top of `fetch_imdb_ratings_csv()` in the Docker
branch:

```python
    if _running_in_docker():
        raise RuntimeError(
            "IMDB URL scraping requires a display and cannot run in Docker with "
            "Playwright Chromium (IMDB blocks non-Chrome browsers). "
            "Please export your ratings from IMDB and upload the CSV file instead."
        )
```

Document the choice in `decisions.md` under `## ST-004 Fix Decisions`.

---

## Fix 2 — Confirm `data/` subdirectory creation (verify, then fix if needed)

Check `app/services/candidates.py`'s `download_datasets()` to confirm it creates
`data/datasets/` before writing files. If it does not:

Add to `app/main.py` in the `lifespan()` function, before the background thread starts:

```python
from pathlib import Path
from app.core.config import get_settings, PROJECT_ROOT

settings = get_settings()
Path(PROJECT_ROOT / settings.data.cache_dir).mkdir(parents=True, exist_ok=True)
(PROJECT_ROOT / "data" / "datasets").mkdir(parents=True, exist_ok=True)
logger.info("Startup: data directories ensured")
```

Only apply this fix if confirmed missing by ST-002 findings.

---

## Fix 3 — Any additional issues from `decisions.md`

Read `## ST-001 Build Findings`, `## ST-002 Startup Findings`, and
`## ST-003 End-to-End Findings` in `decisions.md`. For each error not covered by
Fix 1 or Fix 2, implement a targeted fix and document it in `## ST-004 Fix Decisions`.

---

## Post-conditions

After all fixes, rebuild from the clean clone and re-run the full smoke test:

```bash
cd /c/tmp/imdb-smoke-test
git pull
docker compose down
docker compose up --build -d
```

Wait ~60 s for containers to stabilise, then:

```bash
# API health
curl -s http://localhost:8562/health
# Expected: {"status":"ok"}

# Frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:9137
# Expected: 200

# Pipeline with IMDB URL (wait for datasets to download first)
curl -s -X POST \
  "http://localhost:8562/api/v1/recommendations?imdb_url=https%3A%2F%2Fwww.imdb.com%2Fuser%2Fur38228117%2Fratings%2F" \
  | python -m json.tool | head -20
# Expected: JSON with movies/series/anime keys (not an error object)

# data/ subdirectories
ls /c/tmp/imdb-smoke-test/data/
# Expected: cache/ and datasets/
```

---

## Lint & Tests

Run on every file modified:

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

If `Dockerfile` or `docker-compose.yml` changed, rebuild is the test.

---

## Acceptance Criteria

- [ ] `docker compose up --build` completes without errors from a clean clone
- [ ] `http://localhost:8562/health` returns `{"status":"ok"}`
- [ ] `http://localhost:9137` returns HTTP 200
- [ ] `POST /recommendations?imdb_url=https://www.imdb.com/user/ur38228117/ratings/`
      returns recommendation JSON (movies/series/anime), not an error
- [ ] `data/cache/` and `data/datasets/` created automatically on first startup
- [ ] `uv run ruff check app/` passes with zero new errors
- [ ] `uv run pytest tests/ -q` passes
- [ ] All fix decisions recorded in `decisions.md` under `## ST-004 Fix Decisions`

---

## Commit Message

```
fix: make docker compose up work from a clean clone with IMDB URL
```
