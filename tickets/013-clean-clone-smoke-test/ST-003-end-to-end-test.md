---
ticket: "013"
subtask: 3
title: "End-to-End IMDB URL Test"
status: Open
effort: medium
component: full_stack
depends_on: ["ST-002"]
files_modified: []
files_created: []
---

# SUBTASK 03 — End-to-End Test with IMDB URL

---

## Objective

Run the full recommendation pipeline from inside the Docker environment using the IMDB URL
`https://www.imdb.com/user/ur38228117/ratings/`. Document every failure encountered.
Do not fix anything yet.

---

## Pre-conditions

- ST-002 complete: both containers are running
- API health check returns `{"status":"ok"}`

---

## Steps

### 1. Wait for dataset download

The API downloads IMDB datasets in a background thread at startup. Check progress:

```bash
curl -s http://localhost:8562/api/v1/status | python -m json.tool
```

Wait for datasets to finish downloading. This may take several minutes on first run.
Poll every 30 seconds:

```bash
watch -n 30 'curl -s http://localhost:8562/api/v1/status'
```

If datasets fail to download, record the error.

### 2. Run pipeline with IMDB URL

```bash
curl -s -X POST \
  "http://localhost:8562/api/v1/recommendations?imdb_url=https%3A%2F%2Fwww.imdb.com%2Fuser%2Fur38228117%2Fratings%2F" \
  -H "Content-Type: application/json" \
  2>&1 | tee /c/tmp/pipeline.log
```

This will likely fail — that is expected. Record the exact error.

### 3. Check API logs for the failure reason

```bash
docker compose logs api --tail=50
```

The expected failure is Playwright trying to launch headed Chrome in a container
without a display. Record the exact exception.

### 4. Try the frontend UI

Open `http://localhost:9137` in a browser and attempt the same workflow:
1. Paste `https://www.imdb.com/user/ur38228117/ratings/` in the IMDB URL field
2. Click "Run recommendations"
3. Record what happens (spinner, error message, timeout, etc.)

### 5. Test CSV upload fallback

As a fallback path, test whether CSV upload works in Docker:

```bash
# If you have a watchlist.csv available locally:
curl -s -X POST http://localhost:8562/api/v1/upload-watchlist \
  -F "file=@/path/to/watchlist.csv" \
  | python -m json.tool
```

Record whether this path works as an alternative to the URL scraper.

### 6. Record findings

Document everything in `decisions.md` under `## ST-003 End-to-End Findings`:

- Dataset download: success/failure/time taken
- Pipeline with IMDB URL: exact error message
- API log excerpt showing root cause
- Frontend UI behaviour
- CSV upload: success/failure (if tested)

---

## Acceptance Criteria

- [ ] Dataset download result documented (success or error + message)
- [ ] Pipeline IMDB URL attempt result documented (expected: Playwright/Chrome error)
- [ ] Exact error from API logs captured in `decisions.md`
- [ ] Frontend UI behaviour documented
- [ ] CSV upload fallback result documented if tested

---

## Commit Message

```
chore: document end-to-end smoke test findings (ST-003)
```

(Commit only `decisions.md` additions — no code changes in this subtask.)
