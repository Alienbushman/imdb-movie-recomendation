---
ticket: "013"
subtask: 2
title: "First Startup + Health Check"
status: Open
effort: low
component: full_stack
depends_on: ["ST-001"]
files_modified: []
files_created: []
---

# SUBTASK 02 — `docker compose up` + Health Check

---

## Objective

Start the project with `docker compose up` and verify both containers reach a healthy
state. Document every startup error encountered. Do not fix anything yet.

---

## Pre-conditions

- ST-001 complete: images built successfully (both `api` and `frontend`)
- No `data/` directory pre-seeded — let Docker Compose create it on first mount

---

## Steps

### 1. Start both services

```bash
cd /c/tmp/imdb-smoke-test
docker compose up 2>&1 | tee /c/tmp/startup.log &
```

Wait ~30 seconds for containers to stabilise.

### 2. Check container status

```bash
docker compose ps
```

Expected: both `api` and `frontend` should show `running` or `healthy`.

Record the actual status in `decisions.md`.

### 3. Check the API health endpoint

```bash
curl -s http://localhost:8562/health
# Expected: {"status":"ok"}
```

Record the actual response (or connection error).

### 4. Check the frontend is reachable

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:9137
# Expected: 200
```

### 5. Inspect container logs for errors

```bash
docker compose logs api   2>&1 | grep -i "error\|exception\|traceback\|failed" | head -30
docker compose logs frontend 2>&1 | grep -i "error\|exception\|failed" | head -30
```

### 6. Check that `data/` subdirectories were created

Docker Compose creates `./data` as an empty directory on first mount. The API's startup
background thread calls `download_datasets()`, which should create `data/datasets/` and
`data/cache/`:

```bash
ls -la /c/tmp/imdb-smoke-test/data/
```

Expected: `cache/` and `datasets/` directories created by the API on startup.

### 7. Record findings

Document all errors and unexpected states in `decisions.md` under
`## ST-002 Startup Findings`.

---

## Acceptance Criteria

- [ ] Both containers started (even if unhealthy — document the state)
- [ ] `http://localhost:8562/health` response recorded
- [ ] `http://localhost:9137` HTTP status recorded
- [ ] Container log errors captured in `decisions.md`
- [ ] `data/` subdirectory creation result recorded

---

## Commit Message

```
chore: document first-startup audit (ST-002)
```

(Commit only `decisions.md` additions — no code changes in this subtask.)
