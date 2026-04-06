---
id: "002"
title: "Replace Watchlist CSV with IMDB Ratings URL Input"
status: open
priority: high
component: full_stack
files_affected:
  - app/services/scrape.py
  - app/services/ingest.py
  - app/services/pipeline.py
  - app/api/routes.py
  - app/models/schemas.py
  - frontend/app/composables/useApi.ts
  - frontend/app/pages/index.vue
  - frontend/app/types/index.ts
  - CLAUDE.md
---

# TICKET-002: Replace Watchlist CSV with IMDB Ratings URL Input

---

## Summary

Currently the recommendation pipeline requires a pre-placed `data/watchlist.csv` file on the server's filesystem. There is no way to provide this file through the frontend. Users must manually export their IMDB ratings, then place the CSV in the correct location on the server.

This ticket replaces that workflow with a URL-based approach: the frontend provides a text field where the user enters their IMDB ratings URL (e.g. `https://www.imdb.com/user/ur38228117/ratings/`), the backend extracts the user ID, fetches the CSV export from IMDB, saves it locally, and runs the existing pipeline unchanged.

## Motivation

- The current CSV-based flow requires server filesystem access, making it unusable for anyone accessing the app through the web UI.
- An IMDB ratings URL is simpler for users — they just paste a link instead of exporting, downloading, and placing a file.
- The existing pipeline and model code remain completely unchanged; only the data acquisition step changes.

## Current Architecture

1. User manually exports IMDB ratings as CSV and places it at `data/watchlist.csv`
2. Pipeline step 1 (`ingest.py:load_watchlist`) reads CSV via `pd.read_csv(path)` using column mappings (`Const`, `Your Rating`, `Title`, etc.)
3. Frontend calls `POST /recommendations` — no CSV upload exists in the UI
4. The CSV must already exist on the server's filesystem before the pipeline runs

### CSV Column Structure (from IMDB export)

```
Const,Your Rating,Date Rated,Title,Original Title,URL,Title Type,IMDb Rating,Runtime (mins),Year,Genres,Num Votes,Release Date,Directors
```

## Proposed Architecture

1. User enters their IMDB ratings URL in the frontend
2. Backend extracts user ID from URL (pattern: `ur\d+`)
3. Backend fetches CSV from `https://www.imdb.com/user/{userId}/ratings/export` using `httpx`
4. Backend saves fetched CSV to `data/watchlist.csv` (so subsequent runs don't re-fetch)
5. Pipeline runs as before using the saved CSV

### IMDB URL Fetch Strategy

**Primary approach:** Server-side HTTP GET to `https://www.imdb.com/user/{userId}/ratings/export` with browser-like `User-Agent` and `Accept` headers. This endpoint historically returns the same CSV format as the manual export.

**Why not scrape the HTML page?** The IMDB ratings page at `/user/{userId}/ratings/` is fully JavaScript-rendered (SPA). Scraping would require a headless browser (Selenium/Playwright), which is heavyweight and fragile.

**Why not use IMDB GraphQL?** IMDB's frontend uses `https://graphql.imdb.com/` internally, but the schema is undocumented and could change without notice.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| IMDB blocks `/ratings/export` (403) | Medium | High | Use realistic browser headers; fall back to file upload |
| Private ratings list | Medium | Medium | Return descriptive error asking user to make ratings public |
| IMDB changes CSV format | Low | High | Same risk as today with manual CSV; no additional exposure |
| Rate limiting by IMDB | Low | Low | Fetch happens once per pipeline run; CSV cached to disk |
| Large rating lists / timeout | Low | Low | Set 60s `httpx` timeout; pipeline already handles large watchlists |

## Fallback: File Upload Endpoint

If the IMDB export URL proves unreliable (e.g. requires authentication), a `POST /upload-watchlist` endpoint should be added as a secondary path. The frontend would then show: "Paste your IMDB URL" as primary, with a "Or upload CSV manually" fallback. This fallback is covered in subtask 7.

## Dependencies

- `httpx` is already in `pyproject.toml` — no new Python packages needed
- No new frontend packages needed

## Subtasks

All subtasks are in the [002-replace-csv-with-imdb-url/](002-replace-csv-with-imdb-url/) directory:

| # | Subtask | Effort | Component | Dependencies |
|---|---------|--------|-----------|-------------|
| 1 | [Backend: Create IMDB URL scraper service](002-replace-csv-with-imdb-url/ST-001-backend-scrape-service.md) | Low | Backend | None |
| 2 | [Backend: Modify ingest to accept CSV content string](002-replace-csv-with-imdb-url/ST-002-backend-ingest-csv-content.md) | Low | Backend | None |
| 3 | [Backend: Wire URL through pipeline](002-replace-csv-with-imdb-url/ST-003-backend-pipeline-url-param.md) | Low | Backend | Subtasks 1, 2 |
| 4 | [Backend: Add URL parameter to API routes](002-replace-csv-with-imdb-url/ST-004-backend-api-routes.md) | Low | Backend | Subtask 3 |
| 5 | [Frontend: Update API composable](002-replace-csv-with-imdb-url/ST-005-frontend-api-composable.md) | Low | Frontend | None |
| 6 | [Frontend: Add URL input to UI](002-replace-csv-with-imdb-url/ST-006-frontend-url-input.md) | Low | Frontend | Subtask 5 |
| 7 | [Backend + Frontend: Add CSV file upload fallback](002-replace-csv-with-imdb-url/ST-007-csv-upload-fallback.md) | Medium | Full Stack | Subtask 4 |
| 8 | [Documentation: Update CLAUDE.md](002-replace-csv-with-imdb-url/ST-008-update-documentation.md) | Low | Docs | All above |

### Execution Order

```
Phase 1 (parallel):  Subtask 1 + Subtask 2 + Subtask 5
Phase 2 (sequential): Subtask 3 (depends on 1, 2)
Phase 3 (sequential): Subtask 4 (depends on 3)
Phase 4 (parallel):  Subtask 6 (depends on 5) + Subtask 7 (depends on 4)
Phase 5:             Subtask 8 (depends on all)
```

Subtasks 1, 2, and 5 have no dependencies and can be executed in parallel.
Subtask 6 (frontend UI) depends only on subtask 5 and can run in parallel with subtasks 3-4.

---

## Acceptance Criteria

- [ ] User can paste an IMDB ratings URL in the frontend and receive recommendations
- [ ] Backend extracts user ID, fetches CSV from IMDB, saves to disk, runs pipeline
- [ ] Clear error messages when URL is invalid, ratings are private, or IMDB is unreachable
- [ ] Existing CSV-based flow still works as fallback (no URL = use local file)
- [ ] Fetched CSV is cached to `data/watchlist.csv` so re-runs don't re-fetch
- [ ] File upload fallback exists for when URL fetch fails
- [ ] CLAUDE.md updated to reflect new architecture
