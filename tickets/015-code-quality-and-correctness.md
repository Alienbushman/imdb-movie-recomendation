---
id: "015"
title: "Code Quality and Correctness Fixes"
status: open
priority: medium
component: backend
files_affected:
  - app/services/candidates.py
  - app/services/features.py
  - app/services/model.py
  - app/services/pipeline.py
  - app/core/config.py
  - app/main.py
  - tests/test_candidates.py
---

# TICKET-015: Code Quality and Correctness Fixes

---

## Summary

A codebase audit identified five issues ranging from a silent model correctness
bug to missing test coverage and minor configuration/deployment gaps. No new
features — this ticket is purely fixing what is already there.

---

## Problem Details

### 1. Writer taste features are always zero (ST-001)

Writer taste is one of the explicitly documented model features (4 columns:
`writer_taste_score`, `has_known_writer`, `writer_taste_count`, `writer_taste_mean`).
However they are silently broken: `build_taste_profile()` in `features.py`
populates `writer_avg` by iterating `t.writers` on each rated title, but
`RatedTitle.writers` is always `[]` because the IMDB ratings CSV export does not
include a writers column.

Actors, composers, and cinematographers are handled correctly via a separate
lookup path (the pipeline returns `rated_actors`, `rated_composers`,
`rated_cinematographers` from `load_candidates_from_datasets()`). Writers use
the wrong pattern and need to be aligned with that approach.

### 2. `min_vote_count` code default mismatches config (ST-002)

`config.yaml` sets `min_vote_count: 100` but the Pydantic class in `config.py`
defaults to `10000`. If `config.yaml` is absent (e.g. a broken mount or a
developer running without it), candidates would be filtered to only ~1% of
eligible titles. The YAML should be the single source of truth; the code default
should match it as a safety net.

### 3. No tests for `candidates.py` (ST-003)

`candidates.py` is the largest and most complex service (~900 lines), handling
six TSV joins, name resolution, anime detection, language extraction, and crew
enrichment. It has zero test coverage. A regression in this module silently
corrupts the entire candidate pool with no test failure to catch it.

### 4. CORS is hardcoded to localhost (ST-004)

`app/main.py` hardcodes `allow_origins=["http://localhost:3000",
"http://localhost:9137"]`. Anyone running this on a non-localhost server (LAN,
VPS, Tailscale) hits CORS errors with no clear path to fix it without editing
source. Should be configurable via env var.

### 5. Feature array completeness is not asserted (ST-005)

`feature_vector_to_array()` in `features.py` uses `row.get(name, 0)` for any
feature name not in the dict. This means a feature added to `features_to_dataframe`
but accidentally omitted from `feature_vector_to_array`'s `row` dict will silently
default to `0.0` at inference time — model predicts with wrong data, no error raised.
A single assertion guards against this class of mistake.

---

## Subtasks

| # | File | Title | Effort | Depends On |
|---|------|-------|--------|------------|
| 1 | [ST-001-fix-writer-taste-features.md](015-code-quality-and-correctness/ST-001-fix-writer-taste-features.md) | Fix writer taste features (always zero) | medium | — |
| 2 | [ST-002-align-vote-count-default.md](015-code-quality-and-correctness/ST-002-align-vote-count-default.md) | Align min_vote_count code default with config | low | — |
| 3 | [ST-003-candidates-tests.md](015-code-quality-and-correctness/ST-003-candidates-tests.md) | Add unit tests for candidates.py | high | ST-001 |
| 4 | [ST-004-cors-env-var.md](015-code-quality-and-correctness/ST-004-cors-env-var.md) | CORS allowed origins via env var | low | — |
| 5 | [ST-005-feature-array-assertion.md](015-code-quality-and-correctness/ST-005-feature-array-assertion.md) | Assert feature completeness in feature_vector_to_array | low | — |

---

## Acceptance Criteria

- [ ] `writer_avg` in `TasteProfile` is non-empty after a pipeline run with enough rated titles
- [ ] `min_vote_count` code default matches `config.yaml`
- [ ] `tests/test_candidates.py` exists with tests for join logic, anime detection, and writer lookup
- [ ] CORS origins are configurable via `CORS_ORIGINS` env var (defaults to localhost)
- [ ] `feature_vector_to_array` raises `AssertionError` if a model feature name has no matching row key
- [ ] All existing tests still pass: `uv run pytest tests/ -q`
- [ ] Lint clean: `uv run ruff check app/`

---

## Non-Goals

- No new model features — this ticket fixes existing broken ones
- No frontend changes
- No config.yaml value changes beyond aligning the code default
- No changes to the scored DB or candidate cache schema
