---
ticket: "002"
subtask: 3
title: "Backend: Wire IMDB URL Through Pipeline"
status: open
effort: low
component: backend
depends_on: [1, 2]
files_modified:
  - app/services/pipeline.py
files_created: []
---

# SUBTASK 03: Backend — Wire IMDB URL Through Pipeline

---

## Objective

Modify `run_pipeline()` to accept an optional `imdb_url` parameter. When provided, fetch the CSV from IMDB using the scraper service, save it to disk, and pass the content to the ingest step.

## Context

The pipeline currently orchestrates 4 steps:
1. **Ingest** — `load_watchlist()` reads `data/watchlist.csv`
2. **Model** — Train or load LightGBM model
3. **Candidates** — Load IMDB datasets
4. **Score & Rank** — Predict, filter, categorize

Only step 1 needs to change. When `imdb_url` is provided:
1. Call `fetch_imdb_ratings_csv(imdb_url)` from the new scraper service
2. Save the CSV to `data/watchlist.csv` (so future no-URL runs still work)
3. Pass `csv_content` to `load_watchlist(csv_content=csv_content)`

When `imdb_url` is not provided, the existing behavior is preserved (read from disk).

## Implementation

### 1. Update `run_pipeline` signature

```python
def run_pipeline(
    retrain: bool = False,
    filters: RecommendationFilters | None = None,
    imdb_url: str | None = None,
) -> RecommendationResponse:
```

### 2. Add import

```python
from app.services.scrape import fetch_imdb_ratings_csv, save_ratings_csv
```

### 3. Modify step 1 (ingest)

In the ingest step, before calling `load_watchlist`:

```python
# Step 1: Ingest
if imdb_url:
    csv_content = fetch_imdb_ratings_csv(imdb_url)
    # Save to disk so subsequent runs without URL still work
    watchlist_path = PROJECT_ROOT / settings.data.watchlist_path
    save_ratings_csv(csv_content, watchlist_path)
    rated_titles = load_watchlist(csv_content=csv_content)
else:
    rated_titles = load_watchlist()
```

### 4. Error propagation

Let exceptions from `fetch_imdb_ratings_csv` (`ValueError`, `RuntimeError`) propagate up to the API layer, which will handle them with appropriate HTTP status codes (subtask 4).

## Acceptance Criteria

- [ ] `run_pipeline(imdb_url="https://www.imdb.com/user/ur38228117/ratings/")` fetches CSV from IMDB and runs pipeline
- [ ] Fetched CSV is saved to `data/watchlist.csv`
- [ ] `run_pipeline()` (no URL) still reads from local CSV — existing behavior preserved
- [ ] `ValueError` and `RuntimeError` from scraper propagate to caller
- [ ] Pipeline status updates still work correctly during URL fetch step
- [ ] Steps 2-4 (model, candidates, score) are completely unchanged

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
