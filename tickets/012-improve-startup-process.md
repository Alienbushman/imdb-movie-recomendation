---
id: "012"
title: "Improve Startup Process"
status: open
priority: medium
component: full_stack
files_affected:
  - app/models/schemas.py
  - app/services/candidates.py
  - app/services/pipeline.py
  - frontend/app/types/index.ts
  - frontend/app/components/SetupWizard.vue
  - frontend/app/pages/index.vue
---

# TICKET-012: Improve Startup Process

---

## Summary

Improve the first-run experience so a new user can `docker compose up`, open the browser,
and be guided clearly to connect their IMDB ratings — without hitting confusing errors or
needing to discover hidden UI panels.

---

## Problem Details

The current first-run sequence has several friction points:

1. **Silent failure on first generate** — `loadOrGenerate()` auto-triggers the pipeline on
   page load. With no `data/watchlist.csv` present (fresh install), the pipeline throws a
   `FileNotFoundError` and the UI shows a red error alert with no explanation.

2. **IMDB URL input is hidden** — The URL/CSV input lives inside a collapsible "Data Source"
   panel in the actions bar. First-time users have no reason to expand it.

3. **No dataset download feedback** — The backend downloads ~1 GB of IMDB dataset files in
   the background at startup. The frontend shows nothing during this period; the user can
   click Generate before the datasets are ready and get a confusing error.

4. **No `GET /status` readiness signals** — The status endpoint returns model/candidate
   counts, but nothing about whether datasets are downloaded or a watchlist exists. The
   frontend has no way to distinguish "everything is fine" from "you haven't set anything
   up yet."

---

## Solution

### Backend (ST-001)

Enrich `GET /api/v1/status` with four new boolean fields:

| Field | Meaning |
|---|---|
| `datasets_ready` | All 6 IMDB `.tsv.gz` files exist on disk |
| `datasets_downloading` | Background download thread is active |
| `watchlist_ready` | `data/watchlist.csv` exists and is non-empty |
| `scored_db_ready` | `scored_candidates.db` has rows (fast-path available) |

Track the download thread state with a module-level flag in `candidates.py`, set to `True`
before `download_datasets()` runs and `False` in a `finally` block.

### Frontend (ST-002)

Replace the blind `loadOrGenerate()` call on page mount with a status-aware `initializeApp()`
function:

- If `watchlist_ready` → proceed with existing `loadOrGenerate()` flow (unchanged behaviour
  for returning users)
- If `!watchlist_ready` → show a `SetupWizard` overlay instead of attempting the pipeline

`SetupWizard.vue` guides the user through two steps:

1. **Dataset files** — shows a progress indicator while `datasets_downloading` is true,
   transitions to a green check once `datasets_ready`. The component polls `GET /status`
   every 3 seconds while datasets are still in progress.

2. **Connect your IMDB ratings** — a URL text field and CSV upload, enabled once
   `datasets_ready`. "Get Started" calls `generate(false, url)` and dismisses the wizard
   on success.

---

## Subtasks

| # | File | Title | Effort | Depends On |
|---|------|-------|--------|------------|
| 1 | [ST-001-backend-startup-status.md](012-improve-startup-process/ST-001-backend-startup-status.md) | Backend: Startup readiness fields in `/status` | low | — |
| 2 | [ST-002-frontend-onboarding.md](012-improve-startup-process/ST-002-frontend-onboarding.md) | Frontend: Onboarding wizard for first-time users | medium | 1 |

---

## Acceptance Criteria

- [ ] `GET /api/v1/status` returns `datasets_ready`, `datasets_downloading`,
  `watchlist_ready`, and `scored_db_ready`
- [ ] A fresh `docker compose up` (no `data/` directory) shows a setup wizard, not an error
- [ ] The wizard shows a spinner while datasets are downloading and a check once ready
- [ ] The wizard's "Get Started" button is disabled until `datasets_ready` is true
- [ ] Entering an IMDB URL and clicking "Get Started" runs the pipeline and shows results
- [ ] Uploading a CSV via the wizard also works (same flow)
- [ ] Returning users (watchlist + scored DB present) see the recommendations immediately —
  no wizard, no regression in existing behaviour
- [ ] Lint passes: `uv run ruff check app/` and `cd frontend && npx nuxt typecheck`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`

---

## Non-Goals

- No animated onboarding tour or multi-page setup flow — a single focused card is enough
- No persistent "wizard dismissed" state — the wizard appears only when `!watchlist_ready`
  and disappears automatically once a pipeline run succeeds
- No changes to the backend pipeline logic — only the status endpoint and frontend UX change
- No changes to how datasets are downloaded — the existing background thread in `main.py`
  is unchanged; we only expose its state
