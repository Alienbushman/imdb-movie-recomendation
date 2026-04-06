---
ticket: "001"
subtask: 9
title: "Integrate TMDB API for Keywords, Budget, and Revenue"
status: done
effort: medium-high
component: backend
depends_on: []
files_modified:
  - app/services/candidates.py
  - app/services/features.py
  - app/models/schemas.py
  - config.yaml
files_created:
  - app/services/tmdb.py
---

# SUBTASK 09: Integrate TMDB API for Keywords, Budget, and Revenue

---

## Objective

Integrate the TMDB API to fetch keywords, budget, and revenue for each title, then add keyword affinity features to the model.

## Context

TMDB (The Movie Database) provides a free API with rich metadata not available from IMDB bulk files: **keywords/tags** (e.g., "time travel", "heist", "based on true story"), **budget**, and **revenue**. Keywords are particularly valuable — they capture thematic elements that genres miss entirely.

Free tier: 40 requests/10 seconds. API key configured via environment variable `TMDB_API_KEY`.

## Implementation

### 1. Create `app/services/tmdb.py`

```python
import httpx, json, time
from pathlib import Path

TMDB_BASE = "https://api.themoviedb.org/3"
CACHE_PATH = Path("data/cache/tmdb_metadata.json")

def _find_tmdb_id(imdb_id: str, api_key: str) -> str | None:
    """Map IMDB ID to TMDB ID via /find endpoint."""

def fetch_keywords(tmdb_id: str, media_type: str, api_key: str) -> list[str]:
    """Fetch keyword names via /movie/{id}/keywords or /tv/{id}/keywords."""

def fetch_metadata_batch(
    imdb_ids: list[str],
    api_key: str,
    cache_path: Path = CACHE_PATH,
) -> dict[str, dict]:
    """Fetch and cache TMDB metadata for a list of IMDB IDs.

    Returns dict keyed by imdb_id: {"keywords": [...], "budget": int, "revenue": int}
    Respects rate limits (40 req/10s). Skips IDs already in cache.
    """
```

Rate limiting: track request timestamps and sleep when approaching the limit.

### 2. Add TMDB config

Add to `config.yaml`:
```yaml
tmdb:
  api_key_env: "TMDB_API_KEY"
  cache_path: "data/cache/tmdb_metadata.json"
```

Add corresponding settings to `config.py`.

### 3. Populate `CandidateTitle.keywords`

Add `keywords: list[str]` to `CandidateTitle` schema. Populate from TMDB metadata during candidate loading (only when `TMDB_API_KEY` is set).

### 4. Add keyword affinity features

In `build_taste_profile()` (`features.py`), compute `keyword_avg: dict[str, float]` — mean user rating per keyword (using `RatedTitle.keywords` populated from TMDB data).

Add to `TasteProfile` schema.

In `candidate_to_features()`, compute:
- `keyword_affinity_score`: mean of taste profile affinities for the candidate's keywords (0.0 if none match)
- `has_known_keywords`: 1 if any keyword matched, 0 otherwise
- `keyword_overlap_count`: count of candidate keywords that appear in the user's top-rated titles

### 5. Add to `FeatureVector` and dataframe builders

Add the 3 keyword features to `FeatureVector`, `features_to_dataframe()`, and `feature_vector_to_array()`.

### 6. Graceful degradation

All TMDB-dependent code must check for `TMDB_API_KEY`. When not configured:
- Skip TMDB fetching entirely
- Default all keyword features to 0.0 / 0
- Log a single info message ("TMDB_API_KEY not set, skipping keyword features")

## Acceptance Criteria

- [x] `app/services/tmdb.py` created with `fetch_metadata_batch()` and rate limiting
- [x] TMDB metadata cached to `data/cache/tmdb_metadata.json` (subsequent runs skip API calls)
- [x] `CandidateTitle.keywords` populated when API key is configured
- [x] `TasteProfile.keyword_avg` computed from rated titles' keywords
- [x] 3 keyword features in the model: `keyword_affinity_score`, `has_known_keywords`, `keyword_overlap_count`
- [x] Rate limiting: no more than 40 requests per 10 seconds
- [x] Graceful degradation when `TMDB_API_KEY` is not set
- [x] Documentation note for obtaining and setting `TMDB_API_KEY`

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
