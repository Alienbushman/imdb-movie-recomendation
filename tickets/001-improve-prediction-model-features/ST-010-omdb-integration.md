---
ticket: "001"
subtask: 10
title: "Integrate OMDb API for Rotten Tomatoes and Metacritic Scores"
status: done
effort: medium
component: backend
depends_on: []
files_modified:
  - app/services/features.py
  - app/models/schemas.py
  - config.yaml
files_created:
  - app/services/omdb.py
---

# SUBTASK 10: Integrate OMDb API for Rotten Tomatoes and Metacritic Scores

---

## Objective

Integrate the OMDb API to fetch Rotten Tomatoes and Metacritic scores, then add critic-score and audience/critic-divergence features to the model.

## Context

The OMDb API provides Rotten Tomatoes and Metacritic scores alongside IMDB data. The *gap* between IMDB user rating and critic scores is informative — it captures "audience vs critic disagreement" which correlates with certain taste profiles (e.g. users who love "underrated" films that critics dismissed).

Free tier: 1000 requests/day. API key configured via environment variable `OMDB_API_KEY`.

Endpoint: `http://www.omdbapi.com/?i={imdb_id}&apikey={key}`

Response fields of interest: `Ratings` array containing `{"Source": "Rotten Tomatoes", "Value": "94%"}` and `{"Source": "Metacritic", "Value": "88/100"}`.

## Implementation

### 1. Create `app/services/omdb.py`

```python
import httpx, json
from pathlib import Path

OMDB_BASE = "http://www.omdbapi.com/"
CACHE_PATH = Path("data/cache/omdb_scores.json")

def fetch_scores(imdb_id: str, api_key: str) -> dict:
    """Fetch RT and Metacritic scores for a title.
    
    Returns: {"rt_score": float | None, "metacritic_score": float | None}
    RT score normalized to 0-10 scale. Metacritic score normalized to 0-10 scale.
    """

def fetch_scores_batch(
    imdb_ids: list[str],
    api_key: str,
    cache_path: Path = CACHE_PATH,
) -> dict[str, dict]:
    """Fetch and cache OMDb scores for a list of IMDB IDs.
    
    Skips IDs already in cache. Respects 1000/day limit by tracking calls.
    Returns dict keyed by imdb_id.
    """
```

Score normalization:
- RT: parse `"94%"` → `9.4` (divide by 10)
- Metacritic: parse `"88/100"` → `8.8` (divide by 10)

### 2. Add OMDb config

Add to `config.yaml`:
```yaml
omdb:
  api_key_env: "OMDB_API_KEY"
  cache_path: "data/cache/omdb_scores.json"
```

Add corresponding settings to `config.py`.

### 3. Add score fields to `CandidateTitle`

Add `rt_score: float | None` and `metacritic_score: float | None` to `CandidateTitle` schema. Populate from OMDb cache during candidate loading (only when `OMDB_API_KEY` is set).

### 4. Add 4 features in `candidate_to_features()`

Compute:
- `rt_score`: RT score normalized 0–10 (default 0.0 if missing)
- `metacritic_score`: Metacritic score normalized 0–10 (default 0.0 if missing)
- `imdb_rt_gap`: `imdb_rating - rt_score` (0.0 if either is missing)
- `imdb_metacritic_gap`: `imdb_rating - metacritic_score` (0.0 if either is missing)

### 5. Add to `FeatureVector` and dataframe builders

Add the 4 score features to `FeatureVector`, `features_to_dataframe()`, and `feature_vector_to_array()`.

**Note for training:** RT/Metacritic scores are not available from the IMDB CSV export for rated titles. During training, these features will default to 0.0 (or can be cross-referenced from candidate data by `tconst`). Use 0.0 default so the model learns to discount these features when absent.

### 6. Graceful degradation

When `OMDB_API_KEY` is not set:
- Skip OMDb fetching entirely
- Default all 4 score features to 0.0
- Log a single info message ("OMDB_API_KEY not set, skipping critic score features")

## Acceptance Criteria

- [x] `app/services/omdb.py` created with `fetch_scores_batch()` and caching
- [x] OMDb scores cached to `data/cache/omdb_scores.json`
- [x] `CandidateTitle.rt_score` and `CandidateTitle.metacritic_score` populated when API key is configured
- [x] 4 new features in model: `rt_score`, `metacritic_score`, `imdb_rt_gap`, `imdb_metacritic_gap`
- [x] Missing scores (None) handled gracefully — default to 0.0
- [x] Graceful degradation when `OMDB_API_KEY` is not set
- [x] Documentation note for obtaining and setting `OMDB_API_KEY`

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
