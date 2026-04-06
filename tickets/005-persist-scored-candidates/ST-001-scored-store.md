---
ticket: "005"
subtask: 1
title: "Create SQLite Scored Store"
status: done
effort: low
component: backend
depends_on: []
files_modified: []
files_created:
  - app/services/scored_store.py
---

# SUBTASK 005-01: Create SQLite Scored Store

---

## Context

GET endpoints currently rely on `_state["scored"]` — a large in-memory list of
`(CandidateTitle, FeatureVector, float)` tuples. This is the sole reason the
process holds several GB of RAM after a pipeline run. Replacing it with a SQLite
table eliminates the persistent allocation while keeping GET latency under a second.

---

## Implementation

Create `app/services/scored_store.py` with four public functions:

### Schema (`scored_candidates` table)

```sql
CREATE TABLE IF NOT EXISTS scored_candidates (
    imdb_id             TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    original_title      TEXT,
    title_type          TEXT NOT NULL,
    year                INTEGER,
    genres              TEXT NOT NULL,   -- JSON array: '["Action","Drama"]'
    imdb_rating         REAL NOT NULL,
    num_votes           INTEGER NOT NULL,
    runtime_mins        INTEGER,
    language            TEXT,
    country_code        TEXT,
    directors           TEXT NOT NULL,   -- JSON array
    actors              TEXT NOT NULL,   -- JSON array
    writers             TEXT NOT NULL,   -- JSON array
    composers           TEXT NOT NULL,   -- JSON array
    cinematographers    TEXT NOT NULL,   -- JSON array
    is_anime            INTEGER NOT NULL DEFAULT 0,
    predicted_score     REAL NOT NULL,
    scored_at           TEXT NOT NULL    -- ISO 8601 UTC
)
```

Indexes: `predicted_score DESC`, `title_type`, `language`, `year`,
`(is_anime, predicted_score DESC)`.

### `save_scored(scored: list[tuple[CandidateTitle, float]]) -> None`

- Opens the DB, recreates the schema if needed
- Deletes all existing rows (`DELETE FROM scored_candidates`)
- Bulk-inserts all rows with `executemany`
- `is_anime` is set via `getattr(c, "is_anime", "Animation" in c.genres)` —
  works both before TICKET-004 (genre heuristic) and after (proper `c.is_anime`)

### `has_scored_results() -> bool`

- Returns `False` immediately if the DB file does not exist
- Queries `SELECT 1 FROM scored_candidates LIMIT 1`
- Returns `False` on `sqlite3.OperationalError` (table not yet created)

### `get_scored_count() -> int`

- Returns `SELECT COUNT(*) FROM scored_candidates`
- Used by the `/status` endpoint to report candidate count without a full list

### `query_candidates(filters, title_types, anime_only, top_n, dismissed_ids, min_score) -> list[tuple[CandidateTitle, float]]`

Build a parameterised SQL query:

```sql
SELECT * FROM scored_candidates
WHERE predicted_score >= ?          -- min_score
  AND title_type IN (?, ...)        -- if title_types is not None
  AND is_anime = 1                  -- if anime_only=True
  AND year >= ?                     -- filters.min_year
  AND year <= ?                     -- filters.max_year
  AND language = ?                  -- filters.language
  AND country_code = ?              -- filters.country_code (uppercased)
  AND imdb_rating >= ?              -- filters.min_imdb_rating
  AND (runtime_mins IS NULL OR runtime_mins <= ?)  -- filters.max_runtime
  AND (language IS NULL OR language NOT IN (?,?))  -- filters.exclude_languages
  AND imdb_id NOT IN (?,?,...)      -- dismissed_ids when len <= 500
ORDER BY predicted_score DESC
LIMIT ?                             -- top_n * 10 if genre filters present, else top_n * 2
```

After SQL fetch, apply Python-side genre filters (`filters.genres`,
`filters.exclude_genres`) and large dismissed sets (>500 IDs) then truncate to
`top_n`. Return `list[tuple[CandidateTitle, float]]`.

**DB path:** `PROJECT_ROOT / settings.data.cache_dir / "scored_candidates.db"`

---

## Acceptance Criteria

- [x] `save_scored()` creates the DB + schema on first call, replaces all rows on subsequent calls
- [x] `has_scored_results()` returns `False` when file is absent and `True` after save
- [x] `get_scored_count()` returns correct row count
- [x] `query_candidates()` returns candidates sorted by `predicted_score DESC`
- [x] Genre filters applied in Python when present; scalar filters applied in SQL
- [x] `uv run ruff check app/` passes
- [x] `uv run pytest tests/ -q` passes
