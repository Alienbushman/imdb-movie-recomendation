---
id: ST-001
ticket: "021"
title: "Denormalize title_count and rated_count onto people table"
priority: Medium
risk: low
status: Open
dependencies: []
subsystems: [backend]
---

# ST-001 — Denormalize title_count and rated_count onto People Table

**Priority:** Medium
**Risk:** Low
**Files:** `app/services/scored_store.py`

## Problem

`search_people()` computes `title_count` and `rated_count` via a 3-table JOIN with
GROUP BY and COUNT(DISTINCT) on every search query. These counts only change when
`save_people()` or `save_rated_titles()` runs (i.e. after a pipeline run), so computing
them at query time is wasteful.

## Pre-conditions

```bash
# Confirm current people table has no count columns
grep -A5 "CREATE TABLE IF NOT EXISTS people" app/services/scored_store.py
# Expected: only name_id, name, primary_profession — no title_count or rated_count
```

## Fix

### Step 1 — Add columns to the people table schema

In `_ensure_tables()` in `scored_store.py`, add two columns to the `people` table:

```sql
CREATE TABLE IF NOT EXISTS people (
    name_id            TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    primary_profession TEXT,
    title_count        INTEGER NOT NULL DEFAULT 0,
    rated_count        INTEGER NOT NULL DEFAULT 0
)
```

### Step 2 — Populate counts during save_people()

After the existing `executemany` INSERT into `people`, run an UPDATE that computes
counts from `title_people` and `rated_titles`:

```sql
UPDATE people SET
    title_count = (
        SELECT COUNT(DISTINCT tp.imdb_id)
        FROM title_people tp
        WHERE tp.name_id = people.name_id
    ),
    rated_count = (
        SELECT COUNT(DISTINCT rt.imdb_id)
        FROM title_people tp
        JOIN rated_titles rt ON rt.imdb_id = tp.imdb_id
        WHERE tp.name_id = people.name_id
    )
```

This runs once per pipeline execution (not per search), so the cost is acceptable.

### Step 3 — Simplify search_people() to use pre-computed counts

Replace the current JOIN query with:

```sql
SELECT name_id, name, primary_profession, title_count, rated_count
FROM people
WHERE name LIKE ? COLLATE NOCASE
ORDER BY rated_count DESC, title_count DESC
LIMIT ?
```

This eliminates the JOIN entirely. The `LIKE` scan is still present (fixed in ST-002
with FTS5), but removing the JOIN alone is a significant improvement.

## Anti-patterns

- Do NOT compute counts at query time — the whole point is to pre-compute them.
- Do NOT change the `search_people()` return type — it must still return dicts with
  keys `name_id`, `name`, `primary_profession`, `title_count`. Drop `rated_count` from
  the response if it wasn't previously exposed (check the schema).
- Do NOT delete the `title_people` table or indexes — they're still used by
  `query_titles_by_person()`.

## Post-conditions

```bash
# Confirm people table now has count columns
grep -A8 "CREATE TABLE IF NOT EXISTS people" app/services/scored_store.py
# Expected: title_count and rated_count columns present
```

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

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
perf: denormalize title_count and rated_count onto people table (ST-001)
```
