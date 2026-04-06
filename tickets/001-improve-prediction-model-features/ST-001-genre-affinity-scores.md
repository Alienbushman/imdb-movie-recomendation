---
ticket: "001"
subtask: 1
title: "Genre Affinity Scores"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/features.py
  - app/models/schemas.py
files_created: []
---

# SUBTASK 01: Genre Affinity Scores (User Average Rating per Genre)

---

## Objective

Replace binary genre flags (0/1) with affinity scores representing the user's mean rating per genre, giving the model a much stronger signal than presence/absence alone.

## Context

Currently genre features are binary flags (0/1). The user's actual affinity for each genre — computed as their average rating of titles in that genre — is a much stronger signal. A user who averages 8.5 on Sci-Fi titles vs 5.2 on Romance titles carries information that binary flags cannot express.

- `build_taste_profile()` is in `features.py:38-65`
- `_build_genre_flags()` is in `features.py:68-71`
- `TasteProfile` is defined in `schemas.py`
- `FeatureVector` is defined in `schemas.py`

## Implementation

### 1. Compute genre averages in `build_taste_profile()`

In `build_taste_profile()` (`features.py:38-65`), compute `genre_avg: dict[str, float]` — the user's mean rating per genre from their watchlist. For each rated title, split its genres and accumulate the rating into a per-genre sum and count dict, then divide.

### 2. Add `genre_avg` to `TasteProfile` schema

Add `genre_avg: dict[str, float]` field to the `TasteProfile` schema in `schemas.py`.

### 3. Add affinity features

In `_build_genre_flags()` or a new `_compute_genre_affinity()` function, produce features like:
```
genre_action_affinity = taste_profile.genre_avg.get("Action", 0.0)
```
For all 23 genres (same set as the existing binary flags). Default to `0.0` if the user has no rated titles in that genre.

### 4. Expand `FeatureVector`

Add 23 `genre_X_affinity` fields (one per genre) to `FeatureVector` in `schemas.py`. Include them in `features_to_dataframe()` and `feature_vector_to_array()`.

### 5. Verify model trains

Ensure `model.py` training and prediction work correctly with the expanded feature count.

## Acceptance Criteria

- [x] `TasteProfile` contains a `genre_avg: dict[str, float]` field
- [x] 23 new `genre_X_affinity` features appear in the feature matrix alongside existing binary genre flags
- [x] Affinity defaults to `0.0` when the user has no rated titles in that genre
- [x] Model trains successfully with the new features
- [x] `feature_vector_to_array()` produces a consistent-length array

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
