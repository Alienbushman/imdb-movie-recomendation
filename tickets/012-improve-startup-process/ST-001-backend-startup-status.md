---
ticket: "012"
subtask: 1
title: "Backend: Startup Readiness Fields in /status"
status: Done
effort: low
component: backend
depends_on: []
files_modified:
  - app/models/schemas.py
  - app/services/candidates.py
  - app/services/pipeline.py
files_created: []
---

# SUBTASK 01: Backend — Startup Readiness Fields in `/status`

---

## Objective

Add four new boolean fields to `GET /api/v1/status` so the frontend can determine the
app's startup state and decide whether to show the onboarding wizard.

---

## Pre-conditions

Read these files in full before writing any code:
- `app/models/schemas.py` — understand the existing `PipelineStatus` schema
- `app/services/candidates.py` — understand `download_datasets()` and `DATASET_URLS`
- `app/services/pipeline.py` — understand `get_pipeline_status()`
- `app/services/scored_store.py` — find `has_scored_results()`

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

Both must pass before starting.

---

## Context

`GET /api/v1/status` currently returns `rated_titles_count`, `candidates_count`,
`model_trained`, and `last_run`. The frontend cannot tell from these fields whether:

- The IMDB dataset files have been downloaded yet
- The background download is in progress
- A watchlist CSV exists (pipeline would fail without one)
- There are scored results ready to serve

These four gaps prevent the frontend from showing the right UI state on first load.

---

## Implementation

### 1. Add four fields to `PipelineStatus` in `schemas.py`

```python
# BEFORE — last field is last_run
class PipelineStatus(BaseModel):
    """Snapshot of the current pipeline state."""

    rated_titles_count: int = Field(...)
    candidates_count: int = Field(...)
    model_trained: bool = Field(...)
    last_run: str | None = Field(default=None, ...)
```

```python
# AFTER — add four readiness fields with default=False
class PipelineStatus(BaseModel):
    """Snapshot of the current pipeline state."""

    rated_titles_count: int = Field(
        description="Number of titles loaded from your IMDB export.",
        examples=[2141],
    )
    candidates_count: int = Field(
        description="Number of unseen candidate titles loaded from the IMDB datasets.",
        examples=[11677],
    )
    model_trained: bool = Field(
        description="Whether a taste model is currently loaded in memory.",
        examples=[True],
    )
    last_run: str | None = Field(
        default=None,
        description="ISO 8601 UTC timestamp of the most recent pipeline run.",
        examples=["2026-04-05T14:23:00+00:00"],
    )
    datasets_ready: bool = Field(
        default=False,
        description="Whether all required IMDB dataset files are present on disk.",
    )
    datasets_downloading: bool = Field(
        default=False,
        description="Whether dataset files are currently being downloaded in the background.",
    )
    watchlist_ready: bool = Field(
        default=False,
        description="Whether data/watchlist.csv exists and is non-empty.",
    )
    scored_db_ready: bool = Field(
        default=False,
        description="Whether the scored candidates database has rows (fast-path available).",
    )
```

Use the exact field names, descriptions, and `default=False` as shown.

### 2. Add tracking state and helpers to `candidates.py`

Add a module-level flag and two helper functions. Place them immediately after the existing
module-level constants (after `_PRINCIPAL_CATEGORIES`), before `_dataset_dir()`:

```python
# Module-level download state
_datasets_downloading: bool = False


def is_datasets_downloading() -> bool:
    """Return True if IMDB datasets are currently being downloaded."""
    return _datasets_downloading


def datasets_ready() -> bool:
    """Return True if all required IMDB dataset files exist on disk."""
    dest = _dataset_dir()
    return all((dest / filename).exists() for filename in DATASET_URLS)
```

Then wrap the body of `download_datasets()` with the flag:

```python
# BEFORE
def download_datasets() -> None:
    """Download IMDB dataset files if they don't already exist."""
    dest = _dataset_dir()
    dest.mkdir(parents=True, exist_ok=True)
    logger.info("Dataset directory: %s", dest)

    for filename, url in DATASET_URLS.items():
        ...

    _download_anime_list()
```

```python
# AFTER
def download_datasets() -> None:
    """Download IMDB dataset files if they don't already exist."""
    global _datasets_downloading
    _datasets_downloading = True
    try:
        dest = _dataset_dir()
        dest.mkdir(parents=True, exist_ok=True)
        logger.info("Dataset directory: %s", dest)

        for filename, url in DATASET_URLS.items():
            ...

        _download_anime_list()
    finally:
        _datasets_downloading = False
```

Do not change any other logic inside `download_datasets()`.

### 3. Update `get_pipeline_status()` in `pipeline.py`

```python
# BEFORE
def get_pipeline_status() -> PipelineStatus:
    """Return current pipeline state."""
    from app.services.scored_store import get_scored_count

    return PipelineStatus(
        rated_titles_count=len(_state["titles"]) if _state["titles"] else 0,
        candidates_count=get_scored_count(),
        model_trained=_state["model"] is not None,
        last_run=_state["last_run"],
    )
```

```python
# AFTER
def get_pipeline_status() -> PipelineStatus:
    """Return current pipeline state."""
    from app.services.candidates import datasets_ready as _datasets_ready
    from app.services.candidates import is_datasets_downloading
    from app.services.scored_store import get_scored_count, has_scored_results

    settings = get_settings()
    watchlist_path = PROJECT_ROOT / settings.data.watchlist_path

    return PipelineStatus(
        rated_titles_count=len(_state["titles"]) if _state["titles"] else 0,
        candidates_count=get_scored_count(),
        model_trained=_state["model"] is not None,
        last_run=_state["last_run"],
        datasets_ready=_datasets_ready(),
        datasets_downloading=is_datasets_downloading(),
        watchlist_ready=watchlist_path.exists() and watchlist_path.stat().st_size > 0,
        scored_db_ready=has_scored_results(),
    )
```

Note the alias `_datasets_ready` avoids a name collision with the local variable.

---

## Acceptance Criteria

- [ ] `GET /api/v1/status` response JSON includes `datasets_ready`, `datasets_downloading`,
  `watchlist_ready`, and `scored_db_ready`
- [ ] `datasets_ready` is `true` when all files in `DATASET_URLS` exist in `data/datasets/`
- [ ] `datasets_ready` is `false` when any of those files is missing
- [ ] `datasets_downloading` is `true` while `download_datasets()` is executing; `false`
  before it starts and after it finishes
- [ ] `watchlist_ready` is `true` when `data/watchlist.csv` exists and `stat().st_size > 0`
- [ ] `watchlist_ready` is `false` when the file is missing or empty
- [ ] `scored_db_ready` is `true` when `has_scored_results()` returns `True`
- [ ] All four new fields default to `false` — no regression for clients that don't read them
- [ ] `uv run ruff check app/` passes
- [ ] `uv run pytest tests/ -q` passes

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

No new test files are required for this subtask; the existing smoke tests cover the route.
Manually verify the endpoint after running the backend:

```bash
curl -s http://localhost:8562/api/v1/status | python -m json.tool
```

Confirm all four new fields appear in the response.

---

## Commit Message

```
feat: add startup readiness fields to GET /status
```
