---
ticket: "001"
subtask: 5
title: "Add Title Type as a Model Feature"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/features.py
  - app/models/schemas.py
files_created: []
---

# SUBTASK 05: Add Title Type as a Model Feature

---

## Objective

One-hot encode `title_type` (movie, tvSeries, tvMiniSeries, tvMovie) as model features so it can learn systematic rating differences across title types.

## Context

`title_type` (movie, tvSeries, tvMiniSeries, tvMovie) exists on every `CandidateTitle` and `RatedTitle` but is only used for post-scoring categorization in `recommend.py`. It is never fed to the model. Users may systematically rate certain types higher (e.g. some users rate mini-series more favorably than films).

The title types to encode are the four most common: `movie`, `tvSeries`, `tvMiniSeries`, `tvMovie`. Any other type gets all flags set to 0.

## Implementation

### 1. Add one-hot type flags to `FeatureVector`

Add `type_flags: dict[str, int]` to `FeatureVector` in `schemas.py`, analogous to `genre_flags`. Keys: `type_movie`, `type_tvseries`, `type_tvminiseries`, `type_tvmovie`.

### 2. Compute in feature builder functions

Add a helper `_build_type_flags(title_type: str | None) -> dict[str, int]` in `features.py`:

```python
TYPE_MAP = {
    "movie": "type_movie",
    "tvSeries": "type_tvseries",
    "tvMiniSeries": "type_tvminiseries",
    "tvMovie": "type_tvmovie",
}

def _build_type_flags(title_type: str | None) -> dict[str, int]:
    flags = {v: 0 for v in TYPE_MAP.values()}
    if title_type and title_type in TYPE_MAP:
        flags[TYPE_MAP[title_type]] = 1
    return flags
```

Call this in both `rated_title_to_features()` and `candidate_to_features()`.

### 3. Include in dataframe builders

Expand `features_to_dataframe()` and `feature_vector_to_array()` to include type flags. Ensure column order is deterministic (consistent between training and inference).

## Acceptance Criteria

- [x] 4 binary features `type_movie`, `type_tvseries`, `type_tvminiseries`, `type_tvmovie` in the feature matrix
- [x] Exactly one flag is 1 for known types; all flags are 0 for unknown/other types
- [x] Both `rated_title_to_features()` and `candidate_to_features()` populate type flags
- [x] Model trains and predicts with the expanded feature set
- [x] Column order consistent between training and inference

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
