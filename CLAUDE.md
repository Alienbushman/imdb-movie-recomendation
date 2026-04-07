# IMDB Movie Recommendation Engine

## Architecture Overview

A personalized movie/series recommendation system that learns your taste from your IMDB ratings export and scores unseen titles using a LightGBM ML model.

**Stack**: FastAPI + LightGBM (backend), Nuxt 4 + Vuetify 4 (frontend), Docker Compose

## Project Structure

```
├── app/                    # Python backend (FastAPI)
│   ├── main.py             # FastAPI entry point, lifespan startup, CORS middleware
│   ├── api/routes.py       # All API endpoints
│   ├── core/config.py      # Settings from config.yaml
│   ├── models/schemas.py   # Pydantic request/response models
│   └── services/           # Business logic
│       ├── pipeline.py     # Orchestrates the 4-step pipeline
│       ├── ingest.py       # Parses IMDB watchlist CSV
│       ├── model.py        # LightGBM training & prediction
│       ├── features.py     # Feature engineering (genres, derived)
│       ├── candidates.py   # IMDB dataset loading & caching
│       ├── recommend.py    # Scoring, filtering, ranking, explanations
│       ├── scored_store.py # SQLite persistence for scored candidates
│       ├── dismissed.py    # Persistent dismiss list (JSON file)
│       ├── similar.py      # Cosine-similarity engine for "find similar titles"
│       ├── scrape.py       # Fetches IMDB ratings CSV from user URL
│       ├── tmdb.py         # TMDB API integration (keywords; opt-in via TMDB_API_KEY)
│       └── omdb.py         # OMDb API integration (critic scores; opt-in via OMDB_API_KEY)
├── frontend/               # Nuxt 4 + Vuetify 4 web UI
├── data/                   # Runtime data (not in image, Docker-mounted)
│   ├── watchlist.csv       # User's IMDB ratings (populated via URL fetch, CSV upload, or manual placement)
│   ├── datasets/           # IMDB bulk TSV files (~1GB total, auto-downloaded)
│   │   ├── title.basics.tsv.gz      # Title metadata: type, year, runtime, genres
│   │   ├── title.ratings.tsv.gz     # IMDB vote count and average rating
│   │   ├── title.principals.tsv.gz  # Cast/crew associations per title
│   │   ├── name.basics.tsv.gz       # Person names for principal lookup
│   │   ├── title.akas.tsv.gz        # Alternate titles/regions (language inference)
│   │   └── title.crew.tsv.gz        # Director and writer IDs per title
│   ├── cache/              # Processed candidates JSON + scored SQLite DB
│   ├── taste_model.pkl     # Trained model
│   └── dismissed.json      # Dismissed title IDs
├── config.yaml             # All configuration (filters, model params, categories)
└── docker-compose.yml      # api (port 8562) + frontend (port 9137)
```

## Recommendation Pipeline

The pipeline runs 4 steps in sequence:

1. **Ingest** → Acquire ratings via one of three paths:
   - IMDB URL fetch: backend scrapes `https://www.imdb.com/user/{id}/ratings/export`
   - CSV upload: user uploads manually exported file via `POST /upload-watchlist`
   - Local file: reads `data/watchlist.csv` directly (legacy / Docker workflow)
   Then parse into `RatedTitle` objects.
2. **Model** → Train or load a LightGBM regressor on user ratings (~100+ features: 23 genre affinity flags, 4 director/actor taste, 14 language flags, 4 writer taste, 4 title-type flags, N genre pair interactions, 3 popularity/age, 4 composer/cinematographer taste, 3 TMDB keyword, 4 OMDb critic score)
3. **Candidates** → Load IMDB datasets (basics, ratings, principals, names), merge, filter, cache to JSON
4. **Score & Rank** → Predict scores for all candidates, write to `scored_candidates.db`, build top-N response with explanations

## API Endpoints (prefix: `/api/v1`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/download-datasets` | Download IMDB bulk files |
| POST | `/recommendations` | Run full pipeline; optional `imdb_url` query param to fetch ratings from IMDB |
| POST | `/upload-watchlist` | Accept manually exported IMDB ratings CSV |
| GET | `/recommendations/movies` | Movie recommendations (with filters) |
| GET | `/recommendations/series` | Series recommendations (with filters) |
| GET | `/recommendations/anime` | Anime recommendations (with filters) |
| GET | `/status` | Pipeline state |
| GET | `/health` | Liveness check (used by Docker healthcheck) |
| GET | `/search` | Search titles by name |
| GET | `/similar/{imdb_id}` | Find titles similar to a given title |
| GET | `/people/search` | Search directors and actors by name |
| GET | `/people/{name_id}` | Get all titles for a person |
| POST | `/recommendations/filter` | Re-filter cached results without re-running pipeline |
| POST | `/dismiss/{imdb_id}` | Dismiss a title permanently |
| DELETE | `/dismiss/{imdb_id}` | Restore a dismissed title |
| GET | `/dismissed` | List all dismissed IDs |

## Startup Sequence

`app/main.py` is the FastAPI entry point. On startup (via the `lifespan` context manager):

1. **Cache invalidation** — `invalidate_stale_cache()` runs synchronously. It reads the
   first 16 KB of `data/cache/imdb_candidates.json` and deletes the file if any required
   field (e.g. `is_anime`, `languages`) is absent from the first record. This prevents
   silent stale-cache bugs after schema changes without loading hundreds of MB.

2. **Background dataset download** — a daemon thread starts `download_datasets()`, which
   fetches any missing IMDB TSV files from `datasets.imdbws.com`. The server is fully
   responsive during this download; the thread's state is exposed via the
   `datasets_downloading` flag on `GET /status`.

The server is ready to handle requests immediately after step 1, even while datasets are
still downloading.

## Key Design Decisions

- **SQLite scored store** — `data/cache/scored_candidates.db` persists LightGBM scores after every `POST /recommendations`. GET endpoints query SQLite instead of holding all candidates in memory — keeps post-pipeline RAM under ~500 MB. Delete to force a rescore on next POST.
- **Candidate JSON cache** — `data/cache/imdb_candidates.json` avoids reprocessing ~1GB of IMDB TSV files on every run. Delete it to force a rebuild (needed when `CandidateTitle` schema changes).
- **Lightweight `_state`** — after a pipeline run, `_state` holds only the model, feature names, taste profile, and rated titles (~10 MB total). Large collections (`candidates`, `scored`) are not retained.
- **Runtime filters** — scalar filters applied in SQL; genre filters applied in Python on the small result set.
- **Dismissed IDs** — excluded at query time in `scored_store.query_candidates()` so dismissals take effect immediately without a re-run.
- **Watchlist acquisition** — Three supported paths: IMDB URL (server-side HTTP fetch to the user's public export endpoint), CSV upload (multipart POST), or pre-placed local file. The URL fetch saves the result to `data/watchlist.csv` so subsequent runs without a URL still work.

## Development

```bash
# Backend
uv sync
uv run uvicorn app.main:app --reload --port 8080

# Frontend
cd frontend && npm install && npm run dev

# Docker (both services)
docker compose up --build
```

## Optional Environment Variables

| Variable | Service | Effect |
|----------|---------|--------|
| `TMDB_API_KEY` | `tmdb.py` | Enables TMDB keyword features (`keyword_affinity_score`, `has_known_keywords`, `keyword_overlap_count`). Fetches and caches to `data/cache/tmdb_metadata.json`. Skipped with an info log when absent. |
| `OMDB_API_KEY` | `omdb.py` | Enables critic score features (`rt_score`, `metacritic_score`, `imdb_rt_gap`, `imdb_metacritic_gap`). Fetches and caches to `data/cache/omdb_scores.json`. Skipped with an info log when absent. |

Both APIs are free-tier. Without keys the model trains and predicts normally — those feature columns default to `0.0`.

## Ticket System

### Quick Status

Read `tickets/index.yaml` for the full machine-readable index with all subtask statuses and dependency graphs.

| Ticket | Title | Status |
|--------|-------|--------|
| 001 | Improve prediction model features | **Done** |
| 002 | Replace CSV with IMDB URL | **Done** |
| 003 | Improve frontend UX | **Done** |
| 004 | Animation → Anime rename | **Done** |
| 005 | Persist scored candidates (SQLite) | **Done** |
| 006 | Fast initial page load (skip rescore) | **Done** |
| 007 | Improve language data | **Done** |
| 008 | Client-side sorting + UX polish | **Done** |
| 009 | Find similar movies | **Done** |
| 010 | Frontend component modularization | **Done** |
| 011 | Browse by director or actor | **Done** |
| 012 | Improve startup process | Open |
| 013 | Clean clone smoke test + Docker fix | Open |
| 014 | Documentation audit | **Done** |

### Ticket File Format

All ticket and subtask files use **YAML frontmatter** for machine-parseable metadata:

**Parent tickets** (`tickets/NNN-*.md`):
```yaml
---
id: "NNN"
title: "..."
status: open | in_progress | done
priority: high | medium | low
component: backend | frontend | full_stack | docs
files_affected: [...]
---
```

**Subtask files** (`tickets/NNN-slug/ST-NNN-*.md`):
```yaml
---
id: ST-NNN
ticket: "NNN"
title: "..."
priority: High | Medium | Low
risk: zero | low | medium | high
status: Open | In Progress | Blocked | Done | Won't Do
dependencies: []       # e.g. ["ST-001", "ST-002"]
subsystems: []         # e.g. [backend, frontend]
---
```

### Agent Workflow for Tickets

1. **Orient** — Read `tickets/PROTOCOL.md` (once per session), then `tickets/index.yaml`
2. **Claim** — In `index.yaml`, set the subtask (and parent ticket if `open`) to `in_progress`
3. **Plan** — Read the parent ticket `.md` for context, the ticket's `AGENT.md` for execution order, then the target `ST-NNN-*.md`
4. **Check deps** — Verify all dependencies are `done` in `index.yaml`
5. **Pre-conditions** — Run any `## Pre-conditions` checks in the subtask file
6. **Execute** — Implement per the `## Fix` steps and acceptance criteria
7. **Post-conditions** — Run any `## Post-conditions` checks
8. **Test** — Run the `## Tests` section commands
9. **Commit** — Run `git add` and `git commit` directly using the exact `## Commit Message` from the subtask file. Do NOT ask the user for confirmation before running these commands — the protocol defines what to commit.
10. **Update status** — Update status in three places:
    - Subtask file frontmatter: `status: Done`
    - `tickets/NNN-slug/PROGRESS.md`: Status column → `Done`
    - `tickets/index.yaml`: subtask status → `done`; ticket status → `done` if all subtasks done
11. **Record decisions** — Log non-obvious choices in `tickets/NNN-slug/decisions.md`

## Linting

```bash
uv run ruff check app/          # Python lint
uv run ruff format app/         # Python format
cd frontend && npx nuxt typecheck  # Frontend types
```

The 5 remaining `N806` warnings in `model.py` are intentional (ML convention for uppercase `X` matrix variable).

## Definition of Done

A subtask is complete when **all** of the following are true:

1. All acceptance criteria checkboxes in the subtask file are satisfied
2. Lint passes: `uv run ruff check app/` (backend files) or `cd frontend && npx nuxt typecheck` (frontend files)
3. Smoke tests pass: `uv run pytest tests/ -q`
4. Status updated to `Done` in the ticket's `PROGRESS.md`
5. Any non-obvious implementation choices recorded in the ticket's `decisions.md`

## Gotchas

- **Candidate cache invalidation** — Delete `data/cache/imdb_candidates.json` after any change that adds or renames fields on `CandidateTitle`. The cache is not self-invalidating; a stale cache will silently use old schema.
- **Scored store invalidation** — Delete `data/cache/scored_candidates.db` after any change that affects scoring (feature changes, model retrain). It is rebuilt automatically on the next `POST /recommendations`.
- **Feature array ordering** — `feature_vector_to_array()` must produce columns in the exact same order for both training and inference. Any new field added to `FeatureVector` must appear in both `features_to_dataframe()` and `feature_vector_to_array()`, and the model must be retrained before predictions are valid.
- **N806 lint warnings in model.py** — The 5 `N806` warnings (uppercase `X` variable) are intentional ML convention. Do not rename them or add `# noqa` elsewhere to suppress new warnings.
- **httpx is used synchronously** — The pipeline runs synchronously. Use `httpx.Client` (not `AsyncClient`) for any new HTTP calls in services.
- **Playwright for IMDB scraping** — `scrape.py` uses Playwright with headed Chrome to bypass IMDB's AWS WAF bot detection. The browser must run with `headless=False` and `--disable-blink-features=AutomationControlled`. Headless mode is detected and blocked. IMDB rate-limits after many rapid requests — the scraper adds delays between pages.
- **`data/` is volume-mounted, not in the image** — Any path referencing `data/` must work whether running locally or in Docker. Use `PROJECT_ROOT / settings.data.*` rather than hardcoded paths.
- **Model retraining required after feature changes** — After expanding `FeatureVector`, delete `data/taste_model.pkl` and re-run the pipeline with `retrain=True` to get valid predictions.
