---
id: "005"
title: "Persist Scored Candidates to SQLite"
status: done
priority: high
component: backend
files_affected:
  - app/services/scored_store.py
  - app/services/pipeline.py
  - app/api/routes.py
  - app/services/candidates.py
---

# TICKET-005: Persist Scored Candidates to SQLite to Eliminate In-Memory State

---

## Summary

After a pipeline run the API process holds 10+ GB of RAM because `_state` keeps
`candidates` (50K+ Pydantic objects) and `scored` (50K+ `(CandidateTitle, FeatureVector, float)` tuples) alive indefinitely. They exist only to serve the in-memory filter fast path on GET endpoints.

The fix is to write LightGBM scores — plus all metadata needed to rebuild a
`Recommendation` — to a SQLite database at the end of each pipeline run, then
clear the large in-memory collections. GET filter endpoints query SQLite instead
of re-using in-memory state.

This is appropriate because the project is single-user and low-uptime: a few
seconds per GET request (SQL query + explanation for top-N) is acceptable.

---

## Design

```
POST /recommendations
  → full pipeline (ingest → candidates → model → score)
  → write ALL scored candidates to data/cache/scored_candidates.db
  → clear candidates + scored from _state
  → return top-N response (built immediately from scored list)

GET /recommendations/movies|series|animation
  → query SQLite with SQL WHERE filters (year, language, rating, runtime, ...)
  → Python-side genre filtering on the small result set
  → compute feature vectors + explanations for top-N results only
  → return
```

**`_state` after this ticket (lightweight only):**

| Field | Size | Purpose |
|-------|------|---------|
| `model` | ~5 MB | Feature importances + on-demand explanation for GET |
| `feature_names` | trivial | Feature array ordering |
| `taste_profile` | ~100 KB | `candidate_to_features()` on GET |
| `titles` | ~2 MB | `similar_to` + director-match explanation |
| `seen_ids` | trivial | Exclusion on GET |
| `mae` | trivial | Included in response |
| `last_run` | trivial | Status endpoint |

**Removed from `_state`:** `candidates`, `scored`, `importances`, `rated_features`

---

## Interaction with TICKET-004

TICKET-004 adds `CandidateTitle.is_anime` (whitelist-based) and renames the
`animation` category to `anime`. This ticket:

- Stores `is_anime` as a column in `scored_candidates` from day one. Before
  TICKET-004 is implemented the value is derived as `"Animation" in genres`.
  After TICKET-004, `save_scored()` uses `c.is_anime` directly via
  `getattr(c, "is_anime", "Animation" in c.genres)`.
- Uses `WHERE is_anime = 1` for the animation/anime category query — this
  remains correct in both the pre-004 and post-004 state.
- Route and field names stay as `animation` / `RecommendationResponse.animation`
  until TICKET-004 renames them.

---

## Subtasks

| # | File | Title | Component |
|---|------|-------|-----------|
| 1 | [ST-001-scored-store.md](005-persist-scored-candidates/ST-001-scored-store.md) | Create SQLite scored store | Backend |
| 2 | [ST-002-pipeline-integration.md](005-persist-scored-candidates/ST-002-pipeline-integration.md) | Write scores to DB, slim `_state` | Backend |
| 3 | [ST-003-routes-and-cleanup.md](005-persist-scored-candidates/ST-003-routes-and-cleanup.md) | Route GET endpoints to DB, remove fast path | Backend |
| 4 | [ST-004-candidates-dedup.md](005-persist-scored-candidates/ST-004-candidates-dedup.md) | Deduplicate `name_lookup` load + partial cache check | Backend |

### Execution Order

```
Subtasks 1 and 4 can run in parallel (no dependencies).
Subtask 2 depends on subtask 1 (needs scored_store functions).
Subtask 3 depends on subtask 2 (needs get_recommendations_from_db).
```

---

## Acceptance Criteria

- [ ] `data/cache/scored_candidates.db` is created/updated on every `POST /recommendations`
- [ ] `_state` no longer holds `candidates`, `scored`, `importances`, or `rated_features` after pipeline run
- [ ] GET `/recommendations/movies|series|animation` query SQLite and compute explanations for top-N only
- [ ] `POST /recommendations/filter` queries SQLite (returns 409 if DB not populated)
- [ ] `name.basics.tsv.gz` is loaded only once per pipeline run
- [ ] `invalidate_stale_cache()` reads only the first object (not the full file)
- [ ] RAM after a pipeline run drops to under 500 MB (model + taste state only)
- [ ] Lint passes and smoke tests pass
