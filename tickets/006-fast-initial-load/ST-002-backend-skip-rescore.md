---
id: ST-002
ticket: "006"
title: "Skip Rescore When DB Is Fresh"
priority: High
risk: low
status: Done
dependencies: []
subsystems: [backend]
---

# ST-002 — Skip Rescore When DB Is Fresh

**Priority:** High
**Risk:** Low
**Files:** `app/services/pipeline.py`, `app/api/routes.py`

## Problem

`POST /recommendations` always runs all four pipeline steps including the slow candidate
load (~hundreds of MB JSON deserialisation) and full LightGBM rescore. When
`scored_candidates.db` is populated and no new data source is provided, rescoring produces
identical results — wasting tens of seconds.

## Pre-conditions

```bash
# Confirm run_pipeline exists
grep -n "def run_pipeline" app/services/pipeline.py
# Expected: 1 match

# Confirm generate_recommendations route exists
grep -n "def generate_recommendations" app/api/routes.py
# Expected: 1 match

# Confirm scored_store module exists
grep -rn "def.*scored" app/services/scored_store.py | head -5
# Expected: several function definitions
```

## Fix

Read both files before editing to confirm the current state.

### Step 1 — Ensure `has_scored_results()` exists in `scored_store.py`

If the function does not already exist, add it:

```python
def has_scored_results() -> bool:
    """Return True if scored_candidates.db exists and has at least one row."""
    if not DB_PATH.exists():
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT 1 FROM scored_candidates LIMIT 1").fetchone()
        return row is not None
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()
```

### Step 2 — `pipeline.py` — add guard at top of `run_pipeline()`

Add a `force: bool = False` parameter to `run_pipeline()`. At the start of the function
body, after acquiring the lock, add:

```python
from app.services.scored_store import has_scored_results

if not force and not retrain and imdb_url is None:
    if has_scored_results():
        logger.info(
            "Scored DB already populated and no new data — returning cached results"
        )
        return get_recommendations_from_db(filters=filters)
```

### Step 3 — `routes.py` — expose `force` query param

Add `force: bool = Query(False, description="Force a full pipeline re-run even if cached scores exist.")`
to `generate_recommendations()` and pass it through to `run_pipeline()`.

## Anti-patterns

- Do NOT skip the pipeline when `imdb_url` is provided — new data means a fresh run
- Do NOT skip the pipeline when `retrain=True` — the user explicitly wants a retrain
- Do NOT cache the `has_scored_results()` check in memory — always check the DB on disk
  because it may have been deleted between requests
- Do NOT remove or bypass the existing `_lock` mechanism in the pipeline

## Post-conditions

```bash
# Confirm force parameter exists in run_pipeline
grep -n "force" app/services/pipeline.py
# Expected: at least 2 matches (parameter + guard)

# Confirm force parameter exists in route
grep -n "force" app/api/routes.py
# Expected: at least 1 match

# Confirm has_scored_results exists
grep -n "has_scored_results" app/services/scored_store.py
# Expected: at least 1 match
```

## Tests

```bash
# Backend lint
uv run ruff check app/

# Backend tests
uv run pytest tests/ -q
```

## Files Changed

```
app/services/pipeline.py
app/api/routes.py
app/services/scored_store.py
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: skip pipeline rescore when scored DB is already populated
```
