---
id: ST-003
ticket: "021"
title: "Add FTS5 virtual table for title search"
priority: Medium
risk: medium
status: Open
dependencies: []
subsystems: [backend]
---

# ST-003 — Add FTS5 Virtual Table for Title Search

**Priority:** Medium
**Risk:** Medium
**Files:** `app/services/scored_store.py`

## Problem

`search_titles()` uses `LIKE '%query%'` on both `rated_titles` and `scored_candidates`
via a UNION, forcing full table scans on ~600K+ rows. This is the search used on the
"Find Similar" page to find the seed title.

## Pre-conditions

```bash
# Confirm current search_titles uses LIKE
grep -A15 "def search_titles" app/services/scored_store.py
# Expected: LIKE queries on both tables
```

## Fix

### Step 1 — Create FTS5 virtual tables in _ensure_tables()

Add two FTS5 tables, one for each content table:

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS scored_candidates_fts USING fts5(
    title,
    content='scored_candidates',
    content_rowid='rowid'
);

CREATE VIRTUAL TABLE IF NOT EXISTS rated_titles_fts USING fts5(
    title,
    content='rated_titles',
    content_rowid='rowid'
);
```

### Step 2 — Rebuild FTS indexes in save functions

In `save_scored_candidates()`, after the existing insert:

```python
conn.execute("INSERT INTO scored_candidates_fts(scored_candidates_fts) VALUES('rebuild')")
```

In `save_rated_titles()`, after the existing insert:

```python
conn.execute("INSERT INTO rated_titles_fts(rated_titles_fts) VALUES('rebuild')")
```

### Step 3 — Rewrite search_titles() to use FTS5 with LIKE fallback

Apply the same FTS5-first-then-LIKE-fallback pattern as ST-002:

```python
def search_titles(query: str, limit: int = 20) -> list[dict]:
    fts_query = _fts5_query(query)
    # Try FTS5 first
    if fts_query:
        rows = conn.execute(
            """
            SELECT r.imdb_id, r.title, r.year, r.title_type, 1 AS is_rated, 0 AS num_votes
            FROM rated_titles r
            JOIN rated_titles_fts fts ON fts.rowid = r.rowid
            WHERE rated_titles_fts MATCH ?
            UNION
            SELECT s.imdb_id, s.title, s.year, s.title_type, 0 AS is_rated, s.num_votes
            FROM scored_candidates s
            JOIN scored_candidates_fts fts ON fts.rowid = s.rowid
            WHERE scored_candidates_fts MATCH ?
            ORDER BY is_rated DESC, num_votes DESC
            LIMIT ?
            """,
            (fts_query, fts_query, limit),
        ).fetchall()
        if rows:
            return [dict(r) for r in rows]
    # Fallback to LIKE for substring matches
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
```

### Step 4 — Reuse _fts5_query helper

Use the same `_fts5_query()` function from ST-002. If ST-003 is implemented before
ST-002, define the helper here; otherwise reuse it.

## Anti-patterns

- Do NOT create a single combined FTS table for both rated and scored — they have
  different schemas and different `is_rated` semantics.
- Do NOT drop the UNION structure — rated titles must still sort above scored candidates.
- Do NOT change the response schema.

## Post-conditions

```bash
# Confirm FTS5 tables exist for both scored_candidates and rated_titles
grep "scored_candidates_fts\|rated_titles_fts" app/services/scored_store.py
# Expected: CREATE VIRTUAL TABLE, rebuild, and MATCH for both
```

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

Manually verify:
- On the Similar page, search "inception" — returns the film instantly
- Search "incep" — returns via prefix match
- Search "dark knight" — returns via multi-word match

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
perf: add FTS5 index for title search on similar page (ST-003)
```
