# Agent Instructions — Ticket 013

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for execution.

---

## Goal

Verify the project works end-to-end starting from a clean git clone, with no pre-existing
data, using only `docker compose build` + `docker compose up`. Then fix every breaking
change discovered.

The test IMDB user URL is:
```
https://www.imdb.com/user/ur38228117/ratings/
```

---

## Subtask Order

```
ST-001  ← clone to temp dir + docker compose build (no deps)
ST-002  ← docker compose up + first-startup health check (depends on ST-001)
ST-003  ← end-to-end test: datasets + IMDB URL pipeline (depends on ST-002)
ST-004  ← fix all breaking changes discovered in ST-001–003 (depends on ST-003)
```

Each subtask is both investigative and documentary: run the step, record what breaks,
then continue. ST-004 implements all fixes based on the documented findings.

---

## Ticket-Specific Context

### Temp directory
Use `c:/tmp/imdb-smoke-test` (Windows host). The clone must be fresh — no `data/`,
no `.env`, no pre-built images. Test exactly what a new user would experience.

### Docker constraints
- Only allowed commands: `docker compose build` then `docker compose up`
- No `docker exec` or manual `data/` seeding during the test phase (ST-001–003)
- Fixes in ST-004 may modify the Dockerfile, docker-compose.yml, or source code

### Known risk: Playwright + Chrome in Docker
`scrape.py` uses `channel="chrome"` (requires installed Chrome) and `headless=False`
(requires a display). Neither exists in a standard Docker image. This is expected to be
the primary breaking change. Investigate and fix in ST-004.

### CORS
The frontend proxies all API calls server-side via `frontend/server/routes/api/[...path].ts`
using `API_BACKEND=http://api:8080`. Browser never contacts the API directly, so CORS is
not expected to be an issue.

### Data directory
`.gitignore` excludes `data/cache/`, `data/datasets/`, model files, and `watchlist.csv`.
The `data/` directory itself is not tracked. Docker Compose will create it on first mount.
The API's startup background thread calls `download_datasets()` which should create
subdirectories — verify this works.

### Lint and tests
Run lint and tests only on files you modify in ST-004:
```bash
uv run ruff check app/
uv run pytest tests/ -q
cd frontend && npx nuxt typecheck
```
