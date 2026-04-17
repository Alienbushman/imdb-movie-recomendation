---
id: ST-002
ticket: "021"
title: "Add FTS5 virtual table for people name search"
priority: High
risk: medium
status: Open
dependencies: [ST-001]
subsystems: [backend]
---

# ST-002 — Add FTS5 Virtual Table for People Name Search

**Priority:** High
**Risk:** Medium
**Files:** `app/services/scored_store.py`

## Problem

`search_people()` uses `LIKE '%query%'` which forces a full table scan of the `people`
table (~1M rows with the full IMDB dataset). Even after ST-001 eliminates the JOIN,
the scan itself is slow for type-ahead search.

## Pre-conditions

```bash
# ST-001 must be done — people table should have title_count and rated_count columns
grep "title_count" app/services/scored_store.py
# Expected: column definition in CREATE TABLE and usage in save_people/search_people
```

## Fix

### Step 1 — Create FTS5 virtual table in _ensure_tables()

Add after the `people` table creation:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS people_fts USING fts5(
    name,
    content='people',
    content_rowid='rowid'
);
```

Note: SQLite FTS5 external content tables reference `rowid`. The `people` table uses
`name_id TEXT PRIMARY KEY`, so SQLite auto-generates a `rowid`. This works correctly.

### Step 2 — Rebuild FTS index in save_people()

After the existing `executemany` INSERT and the count UPDATE from ST-001, rebuild:

```python
conn.execute("INSERT INTO people_fts(people_fts) VALUES('rebuild')")
```

The `'rebuild'` command re-reads all rows from the content table and rebuilds the
FTS index. This is safe to call repeatedly and handles INSERT OR REPLACE correctly.

### Step 3 — Rewrite search_people() to use FTS5

Replace the `LIKE` query with an FTS5 MATCH query:

```sql
SELECT p.name_id, p.name, p.primary_profession, p.title_count
FROM people p
JOIN people_fts fts ON fts.rowid = p.rowid
WHERE people_fts MATCH ?
ORDER BY p.rated_count DESC, p.title_count DESC
LIMIT ?
```

The query parameter must be transformed to an FTS5 query string. For type-ahead
search, append `*` to each word for prefix matching:

```python
def _fts5_query(query: str) -> str:
    """Convert a user search string to an FTS5 prefix query.

    Each word gets a trailing * for prefix matching.
    Example: "martin scor" -> "martin* scor*"
    """
    tokens = query.strip().split()
    if not tokens:
        return ""
    return " ".join(f"{t}*" for t in tokens)
```

### Step 4 — Add LIKE fallback for substring matches

FTS5 is word-boundary based — searching "ewman" won't find "Newman". Add a fallback:
if FTS5 returns no results, fall back to the existing `LIKE '%query%'` query. This
keeps the fast path for 99% of searches while preserving substring matching as a
slow fallback.

```python
def search_people(query: str, limit: int = 20) -> list[dict]:
    fts_query = _fts5_query(query)
    # Try FTS5 first
    if fts_query:
        rows = conn.execute(
            "SELECT p.name_id, p.name, p.primary_profession, p.title_count "
            "FROM people p "
            "JOIN people_fts fts ON fts.rowid = p.rowid "
            "WHERE people_fts MATCH ? "
            "ORDER BY p.rated_count DESC, p.title_count DESC "
            "LIMIT ?",
            (fts_query, limit),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]
    # Fallback to LIKE for substring matches
    rows = conn.execute(
        "SELECT name_id, name, primary_profession, title_count "
        "FROM people "
        "WHERE name LIKE ? COLLATE NOCASE "
        "ORDER BY rated_count DESC, title_count DESC "
        "LIMIT ?",
        (f"%{query}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]
```

## Anti-patterns

- Do NOT use `content=''` (contentless FTS) — we need to JOIN back to `people` for the
  count columns.
- Do NOT add triggers for FTS sync — we do bulk inserts via `executemany`, so a single
  `'rebuild'` after insert is cleaner and more reliable.
- Do NOT change the response schema — `search_people()` must return the same dict keys.
- Do NOT remove the LIKE fallback — some users may search by partial last name.

## Post-conditions

```bash
# Confirm FTS5 table creation exists
grep "people_fts" app/services/scored_store.py
# Expected: CREATE VIRTUAL TABLE, rebuild command, and MATCH query
```

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

Manually verify:
- Search "scorsese" — returns Martin Scorsese instantly
- Search "scor" — returns Martin Scorsese via prefix match
- Search "martin scor" — returns Martin Scorsese via multi-word prefix

## Files Changed

```
app/services/scored_store.py
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
perf: add FTS5 index for people name search (ST-002)
```
