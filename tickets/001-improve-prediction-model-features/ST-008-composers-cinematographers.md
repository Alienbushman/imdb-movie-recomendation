---
ticket: "001"
subtask: 8
title: "Expand Principals to Include Composers and Cinematographers"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/candidates.py
  - app/services/features.py
  - app/models/schemas.py
files_created: []
---

# SUBTASK 08: Expand Principals to Include Composers and Cinematographers

---

## Objective

Extract composer and cinematographer data from the already-downloaded `title.principals.tsv.gz` file and add taste features for both, treating them as signals analogous to directors and actors.

## Context

`_load_person_data()` (`candidates.py:301`) filters principals to only `["actor", "actress", "director"]`. The `title.principals.tsv.gz` file also contains entries for `"composer"` and `"cinematographer"`. This data is already downloaded — it just needs to be extracted.

Composers (Hans Zimmer, Ennio Morricone) and cinematographers (Roger Deakins) are real taste signals for film enthusiasts.

The existing director/actor pattern is the exact template to follow.

## Implementation

### 1. Expand `_load_person_data()` categories

In `_load_person_data()` (`candidates.py:301`), extend the category filter to include `"composer"` and `"cinematographer"`. Build `composers_by_title` and `cinematographers_by_title` dicts alongside the existing `actors_by_title` and `directors_by_title`.

Return all four dicts (or refactor to return a single dict keyed by category name).

### 2. Add fields to `CandidateTitle` schema

Add `composers: list[str]` and `cinematographers: list[str]` to `CandidateTitle` in `schemas.py`. Populate during candidate loading.

### 3. Add affinity fields to `TasteProfile`

In `build_taste_profile()` (`features.py`), compute:
- `composer_avg: dict[str, float]` — mean user rating per composer
- `cinematographer_avg: dict[str, float]` — mean user rating per cinematographer

Add both to `TasteProfile` schema in `schemas.py`.

### 4. Add taste features in `_compute_taste_features()`

In `_compute_taste_features()` (`features.py:86-113`), compute:
- `composer_taste_score`: max user rating across the candidate's composers found in taste profile (0.0 if none)
- `has_known_composer`: 1 if any composer found, 0 otherwise
- `cinematographer_taste_score`: max user rating across the candidate's cinematographers (0.0 if none)
- `has_known_cinematographer`: 1 if any cinematographer found, 0 otherwise

### 5. Add to `FeatureVector` and dataframe builders

Add the 4 new fields to `FeatureVector`, `features_to_dataframe()`, and `feature_vector_to_array()`.

### 6. Cache invalidation

Add a check in `candidates.py` that invalidates the candidate cache if the cached data is missing `composers` or `cinematographers` fields on `CandidateTitle`.

## Acceptance Criteria

- [x] `_load_person_data()` extracts composer and cinematographer entries from principals
- [x] `CandidateTitle.composers` and `CandidateTitle.cinematographers` populated
- [x] `TasteProfile.composer_avg` and `TasteProfile.cinematographer_avg` computed from rated titles
- [x] 4 new taste features: `composer_taste_score`, `has_known_composer`, `cinematographer_taste_score`, `has_known_cinematographer`
- [x] Cache invalidation handles the schema change
- [x] Graceful fallback (empty list) when data is missing
- [x] Model trains and predicts with the expanded features

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
