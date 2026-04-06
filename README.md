# IMDB Movie Recommendation Engine

Personalized movie, series, and anime recommendations based on your IMDB rating history. Uses a LightGBM taste model trained on your ratings, with candidates sourced from IMDB's public bulk datasets. Includes a Nuxt 4 + Vuetify 4 web frontend.

## Running with Docker (recommended)

### 1. Provide your IMDB ratings

You have three options (choose one):

- **IMDB URL** (easiest): Use the frontend or pass `imdb_url` to `POST /recommendations` — the backend fetches your ratings automatically
- **CSV upload**: Export your ratings from IMDB and upload via the frontend or `POST /upload-watchlist`
- **Manual placement**: Download the CSV from [IMDB ratings export](https://www.imdb.com/list/ratings/export) and place it at `data/watchlist.csv`

### 2. Build and start

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| API (Swagger docs) | http://localhost:8562/docs |
| Frontend | http://localhost:9137 |

### 3. Download IMDB datasets (first time only)

```bash
curl -X POST http://localhost:8562/api/v1/download-datasets
```

This fetches ~1 GB of IMDB bulk data into `data/datasets/` on your host (mounted as a volume, so it persists across container restarts). Includes title metadata, ratings, cast/crew, and person names.

### 4. Generate recommendations

```bash
curl -X POST http://localhost:8562/api/v1/recommendations
```

Or use the frontend at http://localhost:9137 — click "Generate Recommendations".

---

## Running locally (without Docker)

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+ and npm
- `curl`

### Backend

```bash
uv sync
uv run uvicorn app.main:app --port 8562 --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on http://localhost:3000 and proxies API requests to `localhost:8562`.

Then follow steps 3 and 4 above to download datasets and generate recommendations.

---

## API reference

Interactive docs (Swagger UI) are at `/docs`. ReDoc is at `/redoc`.

| Method | Endpoint | Tag | Description |
|--------|----------|-----|-------------|
| GET | `/health` | Setup | Health check |
| POST | `/api/v1/download-datasets` | Setup | Download IMDB dataset files (~1 GB, run once) |
| GET | `/api/v1/status` | Setup | Pipeline state: titles loaded, model trained, last run |
| POST | `/api/v1/recommendations` | Recommendations | Run full pipeline, return all categories |
| POST | `/api/v1/recommendations?retrain=true` | Recommendations | Force-retrain the taste model |
| GET | `/api/v1/recommendations/movies` | Recommendations | Movie recommendations only |
| GET | `/api/v1/recommendations/series` | Recommendations | Series recommendations only |
| GET | `/api/v1/recommendations/anime` | Recommendations | Anime recommendations only |
| POST | `/api/v1/recommendations/filter` | Recommendations | Re-filter cached scores (no pipeline re-run) |
| POST | `/api/v1/upload-watchlist` | Setup | Upload IMDB ratings CSV manually |
| POST | `/api/v1/dismiss/{imdb_id}` | Dismiss | Dismiss a title permanently |
| DELETE | `/api/v1/dismiss/{imdb_id}` | Dismiss | Restore a dismissed title |
| GET | `/api/v1/dismissed` | Dismiss | List all dismissed IDs |

### Filtering

All recommendation endpoints accept optional query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `min_year` | int | Exclude titles before this year |
| `max_year` | int | Exclude titles after this year |
| `genres` | list[str] | Only include titles matching any of these genres |
| `exclude_genres` | list[str] | Exclude titles matching any of these genres |
| `language` | str | Only include titles in this language |
| `exclude_languages` | list[str] | Exclude titles in any of these languages |
| `min_imdb_rating` | float | Minimum IMDB community rating (0-10) |
| `max_runtime` | int | Maximum runtime in minutes |
| `min_predicted_score` | float | Override the config minimum predicted score (1-10) |
| `top_n_movies` | int | Override number of movie recommendations (0-100) |
| `top_n_series` | int | Override number of series recommendations (0-100) |
| `top_n_anime` | int | Override number of anime recommendations (0-100) |
| `country_code` | str | Only include titles from this country (e.g. `US`, `JP`) |
| `min_vote_count` | int | Minimum IMDB vote count |

Example:

```bash
curl "http://localhost:8562/api/v1/recommendations/movies?min_year=2010&genres=Sci-Fi&genres=Thriller&min_imdb_rating=7.5"
```

### Enriched recommendations

Each recommendation includes:

- **actors** — top 3 billed actors
- **director** — primary director
- **similar_to** — up to 3 titles from your ratings that are similar (by genre overlap)
- **explanation** — human-readable reasons (genre match, director match, actor info, similar titles)

---

## Configuration

Edit `config.yaml` — no code changes needed:

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `imdb_datasets` | `min_vote_count` | `100` | Filter out titles with fewer votes |
| `imdb_datasets` | `min_year` | `1970` | Exclude titles released before this year |
| `imdb_datasets` | `min_rating` | `5.0` | IMDB community rating floor |
| `recommendations` | `top_n_movies` | `20` | How many movie recommendations to return |
| `recommendations` | `top_n_series` | `10` | How many series recommendations to return |
| `recommendations` | `top_n_anime` | `10` | How many anime recommendations to return |
| `recommendations` | `min_predicted_score` | `6.5` | Model score floor for inclusion |
| `model` | `n_estimators` | `200` | LightGBM tree count |

After changing `config.yaml`, restart the server and call `POST /recommendations?retrain=true`.

---

## Architecture

```
app/                            # Python backend (FastAPI)
  api/routes.py                 # All API endpoints
  core/config.py                # Pydantic settings + YAML config loader
  models/schemas.py             # Typed request/response models
  services/
    pipeline.py                 # Orchestrator (4-step pipeline)
    ingest.py                   # Parse IMDB CSV export
    features.py                 # Feature engineering (genres, derived)
    candidates.py               # Load + cache candidates from IMDB bulk datasets
    model.py                    # Train/load/predict with LightGBM
    recommend.py                # Score, filter, rank, and explain recommendations
    scored_store.py             # SQLite persistence for scored candidates
    dismissed.py                # Persistent dismiss list (JSON file)
    scrape.py                   # Fetches IMDB ratings CSV from user URL
    tmdb.py                     # TMDB API integration (keywords; opt-in)
    omdb.py                     # OMDb API integration (critic scores; opt-in)
frontend/                       # Nuxt 4 + Vuetify 4 web UI
  app/pages/index.vue           # Recommendations (tabs, filters, cards)
  app/pages/dismissed.vue       # Manage dismissed titles
  app/components/               # RecommendationCard, FilterDrawer
  app/composables/              # useApi (API client)
data/                           # Runtime data (Docker-mounted, gitignored)
  watchlist.csv                 # Your IMDB export
  datasets/                     # IMDB bulk TSV files
  cache/                        # Processed candidates JSON + scored SQLite DB
  taste_model.pkl               # Trained model
  dismissed.json                # Dismissed title IDs
config.yaml                     # All configuration
docker-compose.yml              # api (8562) + frontend (9137)
```
