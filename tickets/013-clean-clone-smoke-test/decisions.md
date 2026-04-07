# Decisions — Ticket 013

## Static Analysis Findings (pre-smoke-test)

These issues were identified by reading the codebase before running the smoke test.
Confirm each one against the actual runtime errors when executing ST-001–ST-003.

---

### Finding A: Playwright Chrome not runnable in Docker (CRITICAL)

**File**: `app/services/scrape.py`, `Dockerfile`

**Evidence**:
- `scrape.py:242` launches Playwright with `headless=False, channel="chrome"`
- `headless=False` requires an X11/Wayland display — Docker containers have none
- `channel="chrome"` requires system-installed Google Chrome — the Dockerfile installs only
  `curl` and `libgomp1` (`Dockerfile:20`)
- `pyproject.toml:18` lists `playwright>=1.58.0` as a runtime dependency but
  the Dockerfile never runs `playwright install` — so even Playwright's bundled
  Chromium binaries are absent

**Expected runtime error**: Something like:
```
playwright._impl._errors.Error: Executable doesn't exist at /root/.cache/ms-playwright/chromium-*/chrome-linux/chrome
```
or
```
Error: Failed to launch chrome because executable doesn't exist
```

**Impact**: `POST /recommendations?imdb_url=...` fails immediately. The entire IMDB URL
scraping path is broken in Docker.

---

### Finding B: `data/` directory not present in clean clone

**File**: `.gitignore`

**Evidence**:
- `.gitignore` excludes `data/cache/`, `data/datasets/`, `data/taste_model.pkl`,
  `data/dismissed.json`, `data/watchlist.csv` — but not `data/` itself
- Since all contents of `data/` are gitignored, git does not track the directory
- A fresh `git clone` will produce no `data/` directory

**Expected Docker Compose behaviour**: When `docker compose up` runs and the volume
`./data:/app/data` is specified, Docker Compose creates `./data` as an empty directory
automatically. This is standard Docker Compose behaviour.

**Expected API behaviour**: `main.py:21` starts a background thread that calls
`download_datasets()` on startup. `candidates.py`'s download function should create
`data/datasets/` and `data/cache/` via `Path.mkdir(parents=True, exist_ok=True)`.

**Severity**: Probably not a breaking change — Docker creates the dir, API creates subdirs.
Confirm by checking the actual `ls data/` output after startup.

---

### Finding C: CORS restricted to localhost origins

**File**: `app/main.py:101-106`

**Evidence**:
```python
allow_origins=["http://localhost:3000", "http://localhost:9137"]
```

**Expected behaviour**: The frontend proxies all API calls server-side
(`frontend/server/routes/api/[...path].ts`) — the browser never contacts the API directly.
Browser requests go to `http://localhost:9137` (Nuxt server), which then proxies to
`http://api:8080` (internal Docker network). CORS is evaluated at the API level against
the `Origin` header from the browser, which would be `http://localhost:9137` — this IS
in the allowlist.

**Severity**: Not expected to be a breaking change. Confirm during smoke test.

---

### Finding D: Frontend API proxy fallback

**File**: `frontend/server/routes/api/[...path].ts:4`

**Evidence**:
```typescript
const backend = process.env.API_BACKEND || 'http://localhost:8562'
```

In Docker Compose the env var is set to `http://api:8080` (docker-compose.yml:26).
In a clean clone without a `.env` file, this is correct.

**Severity**: Not a breaking change.

---

## ST-001 Build Findings

_To be filled in during execution of ST-001._

## ST-002 Startup Findings

_To be filled in during execution of ST-002._

## ST-003 End-to-End Findings

_To be filled in during execution of ST-003._

## ST-004 Fix Decisions

_To be filled in during execution of ST-004._
