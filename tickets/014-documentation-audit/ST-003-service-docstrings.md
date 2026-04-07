---
id: ST-003
ticket: "014"
title: "Add module-level docstrings to underdocumented services"
priority: Medium
risk: zero
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 03 — Add module-level docstrings to underdocumented services

---

## Objective

Four large service modules have no module-level docstring. Add one to each so a new
reader can understand the module's purpose and key design decisions without reading
the entire file.

---

## Pre-conditions

Confirm each file currently has no module-level docstring (the first non-import token
is not a string literal):

```bash
head -5 app/services/scored_store.py
head -5 app/services/features.py
head -5 app/services/recommend.py
head -5 app/services/candidates.py
```

---

## Fix

### 1. `app/services/scored_store.py`

Read the file first, then insert the following docstring as the very first line of the
file (before any imports):

```python
"""SQLite-backed store for LightGBM-scored candidates.

After each pipeline run, all scored candidates are written to
``data/cache/scored_candidates.db``. GET recommendation endpoints query this
database instead of holding all candidates in memory, keeping post-pipeline
RAM under ~500 MB.

The database also serves person-browse and title-search queries; it stores a
``persons`` table alongside the ``candidates`` table for efficient lookups.

Key functions:
- ``write_candidates`` — bulk-insert or replace all scored rows after a pipeline run
- ``query_candidates`` — paginated, filtered query for the recommendation endpoints
- ``search_titles`` — full-text search for the /search endpoint
- ``search_people`` / ``get_person`` / ``query_titles_by_person`` — person-browse support
- ``has_scored_results`` — fast check used by the startup fast-path
"""
```

### 2. `app/services/features.py`

Read the file first, then insert as the very first line:

```python
"""Feature engineering for the LightGBM taste model.

Converts a ``CandidateTitle`` or ``RatedTitle`` into a flat ``FeatureVector``
dataclass, then serialises it into a numpy array for training and inference.

Feature categories (~100+ total):
- Genre affinity (23 flags) — fraction of user's rated titles that share each genre
- Genre interaction pairs (N) — product of two genre affinity scores for common combos
- Director / actor taste (4) — mean and count of user's ratings for a title's crew
- Writer taste (4) — same as director/actor but for credited writers
- Composer / cinematographer taste (4) — same for below-the-line crew
- Language affinity (14 flags) — fraction of rated titles matching each language
- Title-type flags (4) — movie, short, tvSeries, tvMiniSeries
- Popularity / age (3) — log vote count, title age in years, IMDB average rating
- TMDB keyword affinity (3) — optional; zero-filled when TMDB_API_KEY is absent
- OMDb critic scores (4) — optional; zero-filled when OMDB_API_KEY is absent

IMPORTANT: ``feature_vector_to_array()`` must produce columns in the exact same
order for both training (``features_to_dataframe``) and inference. Adding a new
field requires updating both functions and retraining the model.
"""
```

### 3. `app/services/recommend.py`

Read the file first, then insert as the very first line:

```python
"""Scoring, filtering, ranking, and explanation generation for recommendations.

Takes a trained LightGBM model and a list of candidate titles, predicts a score
for each, applies runtime filters, and returns ranked results with human-readable
explanations.

Key functions:
- ``score_candidates`` — batch-predict scores for all candidates using the model
- ``filter_candidates`` — apply scalar filters (min votes, year, rating) from config
- ``build_recommendations`` — convert scored candidates into ``Recommendation`` objects
  with explanation strings (genre matches, director affinity, etc.)
- ``get_recommendations`` — top-level orchestrator called by the pipeline

Results are persisted to SQLite by ``scored_store.write_candidates`` immediately after
scoring; GET endpoints query the DB directly and do not call this module at serve time.
"""
```

### 4. `app/services/candidates.py`

Read the file first, then insert as the very first line:

```python
"""IMDB bulk dataset loading, filtering, and candidate cache management.

Downloads, parses, and merges the six IMDB TSV files into a list of
``CandidateTitle`` objects representing unseen titles that are eligible for
scoring. The merged result is cached to ``data/cache/imdb_candidates.json``
to avoid reprocessing ~1 GB of data on every pipeline run.

IMDB dataset files (stored in ``data/datasets/``):
- ``title.basics.tsv.gz``   — title metadata (type, year, runtime, genres)
- ``title.ratings.tsv.gz``  — IMDB vote count and average rating
- ``title.principals.tsv.gz`` — cast/crew associations (directors, actors, writers)
- ``name.basics.tsv.gz``    — person names for principal lookup
- ``title.akas.tsv.gz``     — alternate titles and regions (used for language inference)
- ``title.crew.tsv.gz``     — director and writer IDs per title

Cache invalidation: delete ``data/cache/imdb_candidates.json`` after any change
that adds or renames fields on ``CandidateTitle``. The cache is not self-invalidating;
``invalidate_stale_cache()`` checks for a known set of required fields and deletes
the cache automatically if they are missing (run at server startup).

Key functions:
- ``download_datasets`` — fetch all six TSV files from datasets.imdbws.com
- ``load_candidates`` — load from cache or rebuild from raw TSVs
- ``invalidate_stale_cache`` — delete cache if schema is outdated
"""
```

---

## Post-conditions

Verify each file now starts with a docstring:

```bash
python -c "import ast, sys
for f in ['app/services/scored_store.py','app/services/features.py','app/services/recommend.py','app/services/candidates.py']:
    tree = ast.parse(open(f).read())
    doc = ast.get_docstring(tree)
    print(f, 'OK' if doc else 'MISSING')
"
```

Expected: all four lines end with `OK`.

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

Ruff may flag line-length violations in long docstring lines. Wrap any offending lines
to 88 characters.

---

## Files Changed

- `app/services/scored_store.py`
- `app/services/features.py`
- `app/services/recommend.py`
- `app/services/candidates.py`

---

## Commit Message

```
docs: add module-level docstrings to scored_store, features, recommend, candidates (ST-003)
```
