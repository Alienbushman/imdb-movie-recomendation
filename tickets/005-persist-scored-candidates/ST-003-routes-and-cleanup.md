---
ticket: "005"
subtask: 3
title: "Route GET Endpoints to DB + Remove In-Memory Fast Path"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/api/routes.py
files_created: []
---

# SUBTASK 005-03: Route GET Endpoints to DB + Remove In-Memory Fast Path

---

## Context

GET endpoints currently branch on `has_scored_results()` to call either
`filter_recommendations()` (fast, in-memory) or `run_pipeline()` (slow, full
rebuild). After subtask 02, the in-memory path is gone. Both routes converge to
SQLite — `get_recommendations_from_db()` when the DB has data, `run_pipeline()`
on first call (which also populates the DB).

---

## Implementation

### 1. Update imports

Remove `filter_recommendations` and `has_scored_results` from the pipeline import.
Add `get_recommendations_from_db`.
Import `has_scored_results` from `scored_store` instead of pipeline.

```python
from app.services.pipeline import (
    ensure_datasets,
    get_pipeline_status,
    get_recommendations_from_db,
    run_pipeline,
)
from app.services.scored_store import has_scored_results
```

### 2. Update GET endpoints

Replace the `has_scored_results / filter_recommendations` pattern with:

```python
# GET /recommendations/movies
if has_scored_results():
    movies = get_recommendations_from_db(filters=filters).movies
else:
    movies = run_pipeline(filters=filters).movies
```

Same pattern for `/series` and `/animation`.

### 3. Update `POST /recommendations/filter`

Replace the `filter_recommendations()` call with `get_recommendations_from_db()`,
and update the 409 guard to use `has_scored_results()`:

```python
def filter_cached_recommendations(filters: FilterDeps):
    if not has_scored_results():
        raise HTTPException(
            status_code=409,
            detail="No scored results available. Run POST /recommendations first.",
        )
    return get_recommendations_from_db(filters=filters)
```

---

## Acceptance Criteria

- [x] `filter_recommendations` is no longer imported in `routes.py`
- [x] `has_scored_results` is imported from `scored_store`, not `pipeline`
- [x] GET endpoints call `get_recommendations_from_db()` when DB is populated
- [x] GET endpoints call `run_pipeline()` on first call (before DB exists)
- [x] `POST /recommendations/filter` returns 409 when DB is empty
- [x] `uv run ruff check app/` passes
- [x] `uv run pytest tests/ -q` passes
