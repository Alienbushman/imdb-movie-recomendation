---
ticket: "001"
subtask: 3
title: "Add Language as a Model Feature"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/features.py
  - app/services/candidates.py
  - app/models/schemas.py
files_created: []
---

# SUBTASK 03: Add Language as a Model Feature

---

## Objective

Expose language as binary one-hot features in the model so it can learn systematic language preferences (e.g., a user who consistently rates Korean or French films higher).

## Context

Language is loaded from `title.akas.tsv.gz` in `_load_language_data()` (`candidates.py:329-386`) and stored on `CandidateTitle.language`, but it is only used for runtime filtering in `recommend.py`. It is never passed to the model as a feature.

The simplest and most practical approach is option (b) from the ticket: add one-hot binary features for the top 15 languages. During training, cross-reference the candidate dataset to enrich `RatedTitle` with language so the features are non-zero during both training and inference.

## Implementation

### Top 15 languages to encode

```python
TOP_LANGUAGES = [
    "en", "fr", "de", "ja", "ko", "es", "it",
    "hi", "zh", "pt", "sv", "da", "tr", "ru", "Other"
]
```

Features are named `lang_en`, `lang_fr`, ..., `lang_other`. A title whose language is not in the top 14 gets `lang_other = 1`.

### 1. Cross-reference language onto `RatedTitle` during feature building

In `rated_title_to_features()` (`features.py`), the function already receives the rated title. Pass or look up the candidate dataset language map (keyed by IMDB `tconst`) to set the language for each rated title. Alternatively, accept an optional `language: str | None` parameter.

The cleanest approach: in `pipeline.py` (or wherever features are built for training), pass the language from the already-loaded candidate data to `rated_title_to_features()`.

### 2. Add one-hot language features to `FeatureVector`

Add `language_flags: dict[str, int]` to `FeatureVector` (analogous to `genre_flags`).

### 3. Compute in feature builder functions

Add a helper `_build_language_flags(language: str | None) -> dict[str, int]` that returns a dict with exactly one `1` among the top 15 keys (or `lang_other = 1` for unknown/None).

### 4. Include in dataframe builders

Expand `features_to_dataframe()` and `feature_vector_to_array()` to include language flags. Ensure column order is deterministic.

## Acceptance Criteria

- [x] 15 binary language features (`lang_en`, `lang_fr`, ... `lang_other`) appear in the feature matrix
- [x] Exactly one language flag is set to 1 per title
- [x] Language defaults to `lang_other = 1` when language is `None` or not in the top 14
- [x] `RatedTitle` objects have language populated (from candidate cross-reference) during training
- [x] Model trains and predicts with the expanded features
- [x] No regression in existing recommendation behavior

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
