---
ticket: "002"
subtask: 4
title: "Backend: Add IMDB URL Parameter to API Routes"
status: open
effort: low
component: backend
depends_on: [3]
files_modified:
  - app/api/routes.py
files_created: []
---

# SUBTASK 04: Backend — Add IMDB URL Parameter to API Routes

---

## Objective

Add an optional `imdb_url` query parameter to the `POST /recommendations` endpoint and handle the new error cases from the scraper with appropriate HTTP status codes.

## Context

The `POST /recommendations` endpoint currently calls `run_pipeline(retrain=retrain, filters=filters)`. Adding `imdb_url` as a query parameter passes it through to the pipeline. The endpoint must also handle the new failure modes introduced by the IMDB fetch step.

## Implementation

### 1. Add `imdb_url` query parameter

```python
from fastapi import Query

@router.post("/recommendations")
async def run_recommendations(
    retrain: bool = False,
    filters: RecommendationFilters | None = None,
    imdb_url: str | None = Query(
        None,
        description=(
            "IMDB user ratings URL (e.g. https://www.imdb.com/user/ur38228117/ratings/). "
            "If provided, ratings are fetched from IMDB instead of reading the local CSV."
        ),
    ),
) -> RecommendationResponse:
```

### 2. Pass `imdb_url` to pipeline

```python
return run_pipeline(retrain=retrain, filters=filters, imdb_url=imdb_url)
```

### 3. Handle new error cases

Wrap the `run_pipeline` call to catch scraper-specific errors and return appropriate HTTP responses:

```python
from fastapi import HTTPException
import httpx

try:
    return run_pipeline(retrain=retrain, filters=filters, imdb_url=imdb_url)
except ValueError as e:
    # Invalid URL format or user ID
    raise HTTPException(status_code=400, detail=str(e))
except RuntimeError as e:
    # IMDB returned HTTP error (403, 404, etc.)
    raise HTTPException(status_code=502, detail=str(e))
except httpx.TimeoutException:
    raise HTTPException(
        status_code=504,
        detail="Timed out fetching ratings from IMDB. Try again or use CSV upload."
    )
except httpx.ConnectError:
    raise HTTPException(
        status_code=502,
        detail="Could not connect to IMDB. Check your network connection."
    )
```

### 4. No changes to other endpoints

The `GET /recommendations/movies`, `GET /recommendations/series`, and `GET /recommendations/animation` endpoints use cached results from the last pipeline run — they do not need the `imdb_url` parameter. The URL is only relevant when triggering a new pipeline run.

## Acceptance Criteria

- [ ] `POST /recommendations?imdb_url=https://www.imdb.com/user/ur38228117/ratings/` accepted and passed to pipeline
- [ ] `imdb_url` is optional — omitting it preserves existing behavior
- [ ] Invalid URL format → 400 with descriptive message
- [ ] IMDB HTTP error (403/404) → 502 with descriptive message
- [ ] Network timeout → 504 with descriptive message
- [ ] Connection error → 502 with descriptive message
- [ ] Other endpoints (`GET /recommendations/*`) unchanged

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
