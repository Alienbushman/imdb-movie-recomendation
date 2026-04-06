---
ticket: "001"
subtask: 2
title: "Enrich Director/Actor Taste Features"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/features.py
  - app/models/schemas.py
files_created: []
---

# SUBTASK 02: Enrich Director/Actor Taste Features (Count + Mean, Not Just Max)

---

## Objective

Add frequency (count) and mean rating features for directors and actors, supplementing the existing max-based taste score with richer collaborative-filtering signals.

## Context

`_compute_taste_features()` (`features.py:86-113`) currently computes only the `max` taste score for directors and actors. This loses important information:

- **Frequency (count):** A director with 5 rated titles at avg 7.5 is a much stronger signal than one with 1 title at 7.5.
- **Mean vs max:** Max captures "best case" but mean captures consistency. A director whose titles average 8.0 vs one with one 9.0 and three 5.0s are very different signals.

The existing fields `director_taste_score` (max) and `actor_taste_score` (max) are retained — only new fields are added.

## Implementation

### 1. Extend `_compute_taste_features()`

In `_compute_taste_features()` (`features.py:86-113`), compute and return four additional fields:

- `director_taste_count`: number of user-rated titles by the candidate's director(s) found in the taste profile
- `director_taste_mean`: mean of user ratings for those director titles (0.0 if none)
- `actor_taste_count`: number of user-rated titles featuring the candidate's actor(s)
- `actor_taste_mean`: mean of user ratings for those actor titles (0.0 if none)

For directors/actors with no match in the taste profile: count = 0, mean = 0.0.

### 2. Add fields to `FeatureVector`

Add the four new fields to `FeatureVector` in `schemas.py`.

### 3. Update dataframe builders

Include the four new fields in `features_to_dataframe()` and `feature_vector_to_array()`.

## Acceptance Criteria

- [x] 4 new features in the feature vector: `director_taste_count`, `director_taste_mean`, `actor_taste_count`, `actor_taste_mean`
- [x] For directors/actors not in the taste profile, count = 0 and mean = 0.0
- [x] Existing `director_taste_score` (max) and `actor_taste_score` (max) fields are unchanged
- [x] Model trains and predicts with the expanded feature set
- [x] `feature_vector_to_array()` produces a consistent-length array

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
