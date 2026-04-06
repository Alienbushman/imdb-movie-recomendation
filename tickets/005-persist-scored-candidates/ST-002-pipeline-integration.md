---
ticket: "005"
subtask: 2
title: "Write Scores to DB and Slim _state"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/pipeline.py
files_created: []
---

# SUBTASK 005-02: Write Scores to DB and Slim `_state`

---

## Context

`_state` currently caches `candidates`, `scored`, `importances`, and
`rated_features` indefinitely. These exist only to serve the `filter_recommendations()`
fast path. After subtask 01, scores live in SQLite. This subtask removes the
large fields from `_state`, writes to the DB after scoring, and adds
`get_recommendations_from_db()` for the GET endpoints.

---

## Implementation

### 1. Slim `_state` initialisation

Remove `candidates`, `scored`, `importances`, `rated_features` from the dict:

```python
_state: dict = {
    "model": None,
    "feature_names": None,
    "mae": None,
    "taste_profile": None,
    "titles": None,
    "seen_ids": None,
    "last_run": None,
}
```

### 2. `run_pipeline()` — write to DB, update lightweight state

After the `build_recommendations(...)` call, before returning:

```python
from app.services.scored_store import save_scored
save_scored([(c, s) for c, _, s in scored])

_state.update(
    model=model,
    feature_names=feature_names,
    mae=mae,
    taste_profile=taste,
    titles=titles,
    seen_ids=seen_ids,
    last_run=datetime.now(UTC).isoformat(),
)
```

`scored` is the full list from `build_recommendations` (all candidates, not just top-N).

### 3. Remove `filter_recommendations()`

This function is replaced by `get_recommendations_from_db()`. Delete it.

### 4. Remove `has_scored_results()` from this module

It moves to `scored_store.py`. Remove it here; callers will import from there.

### 5. Add `get_recommendations_from_db(filters) -> RecommendationResponse`

```python
import numpy as np

def get_recommendations_from_db(
    filters: RecommendationFilters | None = None,
) -> RecommendationResponse:
    """Build recommendations from SQLite + in-memory taste state.

    Queries SQLite for each category, computes feature vectors and explanations
    only for the small top-N result set. Falls back to loading the taste model
    from disk if _state["model"] is None (e.g. after a server restart).
    """
```

Steps inside:
1. Resolve `model`, `feature_names`, `taste` from `_state` (or reload from disk via `load_taste_model()` if `None`)
2. Determine `min_score`, `top_n_*` from filters/config
3. Build an `_without_animation(f)` helper that adds `"Animation"` to `exclude_genres`
4. Call `query_candidates()` three times:
   - movies: `title_types=movie_cfg.title_types, anime_only=False` + `_without_animation(filters)`
   - series: `title_types=series_cfg.title_types, anime_only=False` + `_without_animation(filters)`
   - animation: `title_types=None, anime_only=True, filters=filters`
5. Precompute `rated_normalized` similarity matrix from `rated_title_to_features` for all `_state["titles"]`
6. For each category, compute per-candidate: `candidate_to_features()`, `_find_similar_rated()`, `_explain_prediction()`
7. Return `RecommendationResponse(movies=..., series=..., animation=..., model_accuracy=...)`

### 6. Update `get_pipeline_status()`

Replace `len(_state["candidates"])` with `get_scored_count()` from `scored_store`:

```python
from app.services.scored_store import get_scored_count

def get_pipeline_status() -> PipelineStatus:
    return PipelineStatus(
        rated_titles_count=len(_state["titles"]) if _state["titles"] else 0,
        candidates_count=get_scored_count(),
        model_trained=_state["model"] is not None,
        last_run=_state["last_run"],
    )
```

---

## Acceptance Criteria

- [x] `_state` no longer contains `candidates`, `scored`, `importances`, `rated_features`
- [x] `save_scored()` is called at the end of every `run_pipeline()` run
- [x] `filter_recommendations()` is removed
- [x] `has_scored_results()` is removed from pipeline.py (imported from scored_store where needed)
- [x] `get_recommendations_from_db()` returns a valid `RecommendationResponse`
- [x] `get_pipeline_status().candidates_count` reflects DB row count
- [x] `uv run ruff check app/` passes
- [x] `uv run pytest tests/ -q` passes
