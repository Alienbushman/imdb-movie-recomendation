---
id: ST-002
ticket: "016"
title: "Persist rated titles to SQLite for durable title search"
priority: High
risk: low
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 02 — Persist rated titles to SQLite for durable title search

---

## Objective

`search_titles` queries only `scored_candidates` (unrated titles). Rated titles (e.g.
Con Air, if the user has rated it) fall back to `_state["titles"]` — an in-memory list
that is reset on server restart. After a restart, rated titles are unsearchable until
the next full pipeline run.

Fix: add a `rated_titles` table to the scored DB, populate it on every pipeline run,
and update `search_titles` to UNION both tables.

---

## Pre-conditions

Confirm the current search only touches scored_candidates:

```bash
grep -n "scored_candidates" app/services/scored_store.py | grep -i "search"
```

Expected: one match for the SELECT in `search_titles` — no `rated_titles` table yet.

---

## Fix

### Step 1 — `app/services/scored_store.py`: add `rated_titles` table to schema

Find `_ensure_schema` and locate the block after the existing `CREATE TABLE` statements
(around line 96, just before `conn.commit()`):

```python
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_title_people_imdb_id ON title_people (imdb_id)"
    )
    conn.commit()
```

Replace with:

```python
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_title_people_imdb_id ON title_people (imdb_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rated_titles (
            imdb_id    TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            year       INTEGER,
            title_type TEXT NOT NULL
        )
    """)
    conn.commit()
```

### Step 2 — `app/services/scored_store.py`: add `write_rated_titles` function

Add this function after `write_people` (around line 533):

```python
def write_rated_titles(titles: list) -> None:
    """Persist the user's rated titles to SQLite for durable title search.

    Clears and repopulates on every pipeline run so the table always reflects
    the current watchlist. Titles are searchable across server restarts without
    requiring a full pipeline re-run.
    """
    conn = _connect()
    try:
        _ensure_schema(conn)
        conn.execute("DELETE FROM rated_titles")
        conn.executemany(
            "INSERT INTO rated_titles (imdb_id, title, year, title_type) VALUES (?,?,?,?)",
            [(t.imdb_id, t.title, t.year, t.title_type) for t in titles],
        )
        conn.commit()
        logger.info("Saved %d rated titles to rated_titles table", len(titles))
    finally:
        conn.close()
```

### Step 3 — `app/services/scored_store.py`: update `search_titles` to UNION both tables

Find the current `search_titles` function:

```python
def search_titles(query: str, limit: int = 20) -> list[dict]:
    """Search scored_candidates by title substring (case-insensitive).

    Returns dicts with keys: imdb_id, title, year, title_type.
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT imdb_id, title, year, title_type FROM scored_candidates "
            "WHERE title LIKE ? COLLATE NOCASE "
            "ORDER BY num_votes DESC "
            "LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
```

Replace with:

```python
def search_titles(query: str, limit: int = 20) -> list[dict]:
    """Search scored_candidates and rated_titles by title substring (case-insensitive).

    Returns dicts with keys: imdb_id, title, year, title_type, is_rated.
    Rated titles are sorted first; within each group, results are ordered by
    vote count descending (num_votes is 0 for rated_titles rows).
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT imdb_id, title, year, title_type, 1 AS is_rated, 0 AS num_votes
            FROM rated_titles
            WHERE title LIKE ? COLLATE NOCASE
            UNION
            SELECT imdb_id, title, year, title_type, 0 AS is_rated, num_votes
            FROM scored_candidates
            WHERE title LIKE ? COLLATE NOCASE
            ORDER BY is_rated DESC, num_votes DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
```

### Step 4 — `app/services/pipeline.py`: call `write_rated_titles` after `save_scored`

Find the import line (~line 149):

```python
        from app.services.scored_store import save_scored, write_people
```

Replace with:

```python
        from app.services.scored_store import save_scored, write_people, write_rated_titles
```

Find the `save_scored` call (~line 151):

```python
        save_scored(scored_candidates)
```

Replace with:

```python
        save_scored(scored_candidates)
        write_rated_titles(titles)
```

### Step 5 — `app/api/routes.py`: read `is_rated` from DB results

Find the search endpoint's DB-hit loop (~line 215):

```python
    for row in db_hits:
        results_by_id[row["imdb_id"]] = TitleSearchResult(
            imdb_id=row["imdb_id"],
            title=row["title"],
            year=row["year"],
            title_type=row["title_type"],
            is_rated=False,
        )
```

Replace with:

```python
    for row in db_hits:
        results_by_id[row["imdb_id"]] = TitleSearchResult(
            imdb_id=row["imdb_id"],
            title=row["title"],
            year=row["year"],
            title_type=row["title_type"],
            is_rated=bool(row["is_rated"]),
        )
```

The in-memory `_state["titles"]` pass (step 2 in the same function) continues to
override with `is_rated=True`, so this is safe even when both paths fire.

---

## Post-conditions

After the fix, `write_rated_titles` is imported and called:

```bash
grep -n "write_rated_titles" app/services/pipeline.py app/services/scored_store.py
```

Expected: one match in `pipeline.py` (call site), two matches in `scored_store.py`
(function definition + `_ensure_schema` table creation).

Confirm `search_titles` UNION:

```bash
grep -n "rated_titles" app/services/scored_store.py
```

Expected: matches in `_ensure_schema`, `write_rated_titles`, and `search_titles`.

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

All existing tests must pass with zero new failures.

---

## Files Changed

- `app/services/scored_store.py`
- `app/services/pipeline.py`
- `app/api/routes.py`

---

## Commit Message

```
fix: persist rated titles to SQLite so title search survives server restarts (ST-002)
```
