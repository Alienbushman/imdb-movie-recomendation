---
id: "006"
title: "Fast Initial Page Load"
status: done
priority: high
component: full_stack
files_affected:
  - frontend/app/pages/index.vue
  - frontend/app/stores/recommendations.ts
  - frontend/nuxt.config.ts
  - frontend/package.json
  - app/services/pipeline.py
---

# TICKET-006: Fast Initial Page Load — Skip Full Pipeline When Scores Are Cached

---

## Problem

Every browser hard reload triggers the full 4-step recommendation pipeline, even
when `scored_candidates.db` already contains valid scores from a previous run.

Root cause — two compounding issues:

**1. Frontend always calls `POST /recommendations` on mount**

`onMounted(() => recommendations.generate())` in `index.vue` calls `generate()`,
which unconditionally calls `POST /recommendations` (full pipeline). The fast path
(`POST /recommendations/filter`) is only used by `applyFilters()`, and
`pipelineReady` resets to `false` on every page reload (in-memory Pinia state), so
even `applyFilters()` would fall back to `generate()`.

**2. Full pipeline re-scores everything even when nothing changed**

`run_pipeline()` in `pipeline.py` always:
- Deserialises the entire `imdb_candidates.json` cache into tens of thousands of
  Pydantic objects (hundreds of MB of JSON)
- Runs LightGBM inference on every candidate
- Rewrites the entire `scored_candidates.db`

...even when the watchlist, model, and dataset haven't changed since the last run.

The fast path — `get_recommendations_from_db()` — is available and completes in
under a second, but is never used on initial page load.

---

## Solution

### Frontend fix (highest impact)

Two parts working together:

**Part A — persisted `pipelineReady`**

Install `@pinia-plugin-persistedstate/nuxt` and persist `pipelineReady` (and
`lastOperation`) from the recommendations store to `localStorage`. This means the
store survives a browser hard reload: if the user has run the pipeline before,
`pipelineReady` is already `true` when the page mounts.

**Part B — `loadOrGenerate()` on mount**

Change the page load strategy: on mount, **try the fast path first** and only run
the full pipeline if there are no cached scores yet.

```
onMounted:
  1. Call POST /recommendations/filter (fast path)
  2. If 409 → no cached scores → fall back to POST /recommendations (full run)
  3. On success → mark pipelineReady = true (also persisted)
```

The two parts reinforce each other:
- Persisted `pipelineReady = true` means `applyFilters()` also uses the fast path
  immediately on reload (e.g. if the user changes a filter before the mount
  request completes).
- `loadOrGenerate()` provides the 409 fallback for when the DB was deleted or the
  server is fresh, resetting `pipelineReady` correctly.

Add `loadOrGenerate()` to the store and call it from `onMounted` instead of
`generate()`. The existing "Generate" and "Retrain" buttons continue to call
`generate()` directly and always trigger a full run.

### Backend guard (secondary, defence-in-depth)

`POST /recommendations` currently re-runs all four pipeline steps unconditionally.
Add a `force` query parameter (default `false`). When `force=false` and
`scored_candidates.db` already exists with results, skip steps 2 and 4 (candidate
loading + scoring) and call `get_recommendations_from_db()` directly instead.

This means even if the frontend accidentally calls `POST /recommendations` when
scores exist, the backend avoids the expensive work.

The full pipeline still runs when:
- `retrain=true`
- `imdb_url` is supplied (new data source)
- `scored_candidates.db` is absent or empty
- `force=true` is explicitly passed

---

## Subtasks

| # | File | Title | Component |
|---|------|-------|-----------|
| 1 | [ST-001-frontend-fast-load.md](006-fast-initial-load/ST-001-frontend-fast-load.md) | Try fast path on page mount | Frontend |
| 2 | [ST-002-backend-skip-rescore.md](006-fast-initial-load/ST-002-backend-skip-rescore.md) | Skip rescore when DB is fresh | Backend |

### Execution Order

```
Subtasks 1 and 2 are independent — run in parallel.
```

---

## Acceptance Criteria

- [ ] Hard reloading the page when `scored_candidates.db` exists completes in under
      3 seconds (fast-path query only, no pipeline run)
- [ ] `pipelineReady` and `lastOperation` survive a browser hard reload via
      `localStorage` persistence
- [ ] "Generate" button always triggers the full pipeline (no change to existing behaviour)
- [ ] "Retrain Model" button always triggers the full pipeline with `retrain=true`
- [ ] First load (no DB, fresh `localStorage`) still falls back to the full pipeline
      automatically
- [ ] If `scored_candidates.db` is deleted between sessions, `loadOrGenerate()` gets
      a 409 and falls back to the full pipeline; `pipelineReady` is reset correctly
- [ ] `POST /recommendations` with `force=false` (default) skips rescore when DB
      is already populated and no new data source is provided
- [ ] The "from cache" chip shows in the UI after a fast initial load
- [ ] Lint passes: `cd frontend && npx nuxt typecheck` and `uv run ruff check app/`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`
