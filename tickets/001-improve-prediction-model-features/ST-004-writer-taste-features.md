---
ticket: "001"
subtask: 4
title: "Add Writer Taste Features"
status: done
effort: medium
component: backend
depends_on: []
files_modified:
  - app/services/candidates.py
  - app/services/features.py
  - app/models/schemas.py
  - config.yaml
files_created: []
---

# SUBTASK 04: Add Writer Taste Features via title.crew.tsv.gz

---

## Objective

Download and integrate `title.crew.tsv.gz` from IMDB to add writer-based taste features (e.g., Aaron Sorkin, Charlie Kaufman). Writers are a strong taste signal not currently used.

## Context

IMDB publishes `title.crew.tsv.gz` containing writer/director relationships per title. This file is not currently downloaded or used. The existing actor/director taste feature pipeline in `candidates.py` and `features.py` provides the pattern to follow.

- `DATASET_URLS` is in `candidates.py:14`
- `_load_person_data()` is in `candidates.py:301` — model new `_load_writer_data()` on this
- `build_taste_profile()` computes director/actor averages — add writer averages analogously
- `_compute_taste_features()` (`features.py:86-113`) — add writer taste computation here

The crew file schema: `tconst \t directors \t writers` where `writers` is a comma-separated list of `nconst` IDs.

## Implementation

### 1. Add dataset URL

In `candidates.py:14`, add:
```python
"title.crew.tsv.gz": "https://datasets.imdbws.com/title.crew.tsv.gz"
```

### 2. Update config

Add `title_crew: "data/datasets/title.crew.tsv.gz"` to `imdb_datasets` in `config.yaml` and add the corresponding field to `ImdbDatasetSettings` in `config.py`.

### 3. Create `_load_writer_data()`

Create `_load_writer_data(title_ids: set[str]) -> dict[str, list[str]]` in `candidates.py`. Parse the crew file, extract `writers` column for each `tconst` in `title_ids`, split by comma, resolve `nconst` IDs to names using the already-loaded `name.basics` dataset. Return `{tconst: [writer_name, ...]}`.

### 4. Add `writers` field to schemas

Add `writers: list[str]` to both `CandidateTitle` and `RatedTitle` in `schemas.py`. Populate `CandidateTitle.writers` from `_load_writer_data()` during candidate loading. For `RatedTitle`, populate during ingest cross-reference (same pattern as language enrichment).

### 5. Add writer affinity to `TasteProfile`

In `build_taste_profile()` (`features.py`), compute `writer_avg: dict[str, float]` — mean user rating per writer name, analogous to `director_avg`.

### 6. Add writer taste features

In `_compute_taste_features()` (`features.py:86-113`), compute:
- `writer_taste_score`: max user rating for any of the candidate's writers found in taste profile (0.0 if none)
- `has_known_writer`: 1 if any writer found, 0 otherwise
- `writer_taste_count`: number of user-rated titles by the candidate's writer(s)
- `writer_taste_mean`: mean user rating for those writer titles (0.0 if none)

### 7. Add to `FeatureVector` and dataframe builders

Add the 4 new writer features to `FeatureVector`, `features_to_dataframe()`, and `feature_vector_to_array()`.

### 8. Cache invalidation

Add a check in `candidates.py` that invalidates the candidate cache if the cached data is missing the `writers` field on `CandidateTitle`.

## Acceptance Criteria

- [x] `title.crew.tsv.gz` is listed in `DATASET_URLS` and downloaded with other datasets
- [x] Writer names are resolved from `nconst` IDs using `name.basics`
- [x] `CandidateTitle.writers` and `RatedTitle.writers` fields populated
- [x] `TasteProfile.writer_avg` computed from rated titles
- [x] 4 writer taste features in the model: `writer_taste_score`, `has_known_writer`, `writer_taste_count`, `writer_taste_mean`
- [x] Cache invalidation handles the schema change (stale cache missing `writers` is rebuilt)
- [x] Graceful fallback (empty list) when writer data is unavailable
- [x] Model trains and predicts with the expanded features

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
