# Agent Instructions — Ticket 021

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for implementation.

---

## Goal

Replace `LIKE '%query%'` full table scans in `search_people()` and `search_titles()`
with SQLite FTS5 virtual tables for near-instant search. Denormalize people counts to
eliminate the expensive 3-table JOIN.

---

## Subtask Order

```
ST-001  ← denormalize people counts (no deps)
ST-002  ← FTS5 for people search (depends on ST-001)
ST-003  ← FTS5 for title search (no deps, parallel with ST-001/002)
ST-004  ← frontend debounce reduction (depends on ST-002 and ST-003)
```

ST-001 and ST-003 can be worked in parallel. ST-002 depends on ST-001 (the denormalized
counts feed the new search query). ST-004 is a small frontend polish after both backend
subtasks are done.

---

## Ticket-Specific Context

### Current schema (relevant tables)

```sql
CREATE TABLE people (
    name_id TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    primary_profession TEXT
);

CREATE TABLE title_people (
    imdb_id TEXT NOT NULL,
    name_id TEXT NOT NULL,
    role    TEXT NOT NULL,
    PRIMARY KEY (imdb_id, name_id, role)
);

CREATE TABLE rated_titles (
    imdb_id      TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    year         INTEGER,
    title_type   TEXT NOT NULL,
    imdb_rating  REAL,
    num_votes    INTEGER NOT NULL DEFAULT 0,
    runtime_mins INTEGER,
    genres       TEXT NOT NULL DEFAULT '[]',
    languages    TEXT NOT NULL DEFAULT '[]',
    user_rating  REAL NOT NULL
);

CREATE TABLE scored_candidates (
    imdb_id      TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    year         INTEGER,
    title_type   TEXT NOT NULL,
    predicted_score REAL NOT NULL,
    imdb_rating  REAL,
    num_votes    INTEGER NOT NULL DEFAULT 0,
    runtime_mins INTEGER,
    genres       TEXT NOT NULL DEFAULT '[]',
    languages    TEXT NOT NULL DEFAULT '[]',
    ...
);
```

### FTS5 external content pattern

FTS5 external content tables avoid duplicating data. The pattern:

```sql
CREATE VIRTUAL TABLE people_fts USING fts5(
    name,
    content='people',
    content_rowid='rowid'
);
```

Population happens via triggers or explicit INSERT after the content table is populated.
Since we bulk-insert via `executemany`, explicit rebuild after insert is simplest:

```sql
INSERT INTO people_fts(people_fts) VALUES('rebuild');
```

### Write paths to instrument

- `save_people()` — after inserting into `people`, rebuild `people_fts`
- `save_scored_candidates()` — after inserting into `scored_candidates`, rebuild title FTS
- `save_rated_titles()` — after inserting into `rated_titles`, rebuild title FTS

### Lint and test commands

```bash
uv run ruff check app/
uv run ruff format app/
cd frontend && npx nuxt typecheck
uv run pytest tests/ -q
```
