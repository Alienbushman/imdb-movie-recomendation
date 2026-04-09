---
id: ST-002
ticket: "018"
title: "Enrich rated_titles table and UNION into query_titles_by_person"
priority: High
risk: medium
status: Open
dependencies: [ST-001]
subsystems: [backend]
---

# SUBTASK 02 — Enrich rated_titles table and UNION into query_titles_by_person

---

## Objective

Even after ST-001 indexes rated-title crew in `title_people`, clicking through to a
person still shows 0 results because `query_titles_by_person` only JOINs
`scored_candidates` — rated titles are not in that table.

Fix:
1. Migrate `rated_titles` schema: add display columns (genres, imdb_rating, num_votes,
   runtime_mins, languages, user_rating) via additive `ALTER TABLE ADD COLUMN`.
2. Enrich `write_rated_titles` to write those new columns.
3. Rewrite `query_titles_by_person` to UNION scored candidates with rated titles.
4. Add `is_rated` flag to the result rows so ST-003 can show a "Seen" badge.
5. Add `is_rated: bool = False` to `PersonTitleResult` in `schemas.py`.
6. Pass `is_rated` in the route handler (`routes.py`).

---

## Pre-conditions

Current `rated_titles` schema (from `_ensure_schema`):

```sql
CREATE TABLE IF NOT EXISTS rated_titles (
    imdb_id    TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    year       INTEGER,
    title_type TEXT NOT NULL
)
```

Only 4 columns — no display metadata.

---

## Fix

### Step 1 — `app/services/scored_store.py`: migrate rated_titles schema

In `_ensure_schema`, replace the `rated_titles` CREATE block with:

```python
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rated_titles (
            imdb_id      TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            year         INTEGER,
            title_type   TEXT NOT NULL,
            imdb_rating  REAL,
            num_votes    INTEGER NOT NULL DEFAULT 0,
            runtime_mins INTEGER,
            genres       TEXT NOT NULL DEFAULT '[]',
            languages    TEXT NOT NULL DEFAULT '[]',
            user_rating  REAL
        )
    """)
    # Additive migration for existing databases
    for col, ddl in [
        ("imdb_rating",  "REAL"),
        ("num_votes",    "INTEGER NOT NULL DEFAULT 0"),
        ("runtime_mins", "INTEGER"),
        ("genres",       "TEXT NOT NULL DEFAULT '[]'"),
        ("languages",    "TEXT NOT NULL DEFAULT '[]'"),
        ("user_rating",  "REAL"),
    ]:
        try:
            conn.execute(f"ALTER TABLE rated_titles ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass  # column already exists
```

### Step 2 — `app/services/scored_store.py`: enrich write_rated_titles

Replace the current `write_rated_titles` implementation:

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
            "INSERT INTO rated_titles "
            "(imdb_id, title, year, title_type, imdb_rating, num_votes, runtime_mins, genres, languages, user_rating) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    t.imdb_id,
                    t.title,
                    t.year,
                    t.title_type,
                    t.imdb_rating,
                    t.num_votes,
                    t.runtime_mins,
                    json.dumps(t.genres),
                    json.dumps([t.language] if t.language else []),
                    float(t.user_rating),
                )
                for t in titles
            ],
        )
        conn.commit()
        logger.info("Saved %d rated titles to rated_titles table", len(titles))
    finally:
        conn.close()
```

### Step 3 — `app/services/scored_store.py`: UNION rated titles in query_titles_by_person

Replace the entire `query_titles_by_person` function:

```python
def query_titles_by_person(
    name_id: str,
    limit: int = 100,
    min_year: int | None = None,
    max_year: int | None = None,
    min_rating: float | None = None,
    min_votes: int | None = None,
    max_runtime: int | None = None,
    dismissed_ids: set[str] | None = None,
) -> tuple[int, list[dict]]:
    """Return (total_count, rows) for titles featuring name_id.

    UNIONs scored candidates (unrated) with rated titles so both appear.
    Rows include all scored_candidates columns plus `roles_csv` and `is_rated`.
    Results are ordered by predicted_score DESC.
    """
    db = _db_path()
    if not db.exists():
        return 0, []
    conn = _connect()
    try:
        # Build shared filter fragments for each branch
        sc_where: list[str] = ["tp.name_id = ?"]
        sc_params: list = [name_id]
        rt_where: list[str] = ["tp.name_id = ?"]
        rt_params: list = [name_id]

        if min_year is not None:
            sc_where.append("sc.year >= ?")
            sc_params.append(min_year)
            rt_where.append("rt.year >= ?")
            rt_params.append(min_year)
        if max_year is not None:
            sc_where.append("sc.year <= ?")
            sc_params.append(max_year)
            rt_where.append("rt.year <= ?")
            rt_params.append(max_year)
        if min_rating is not None:
            sc_where.append("sc.imdb_rating >= ?")
            sc_params.append(min_rating)
            rt_where.append("rt.imdb_rating >= ?")
            rt_params.append(min_rating)
        if min_votes is not None:
            sc_where.append("sc.num_votes >= ?")
            sc_params.append(min_votes)
            rt_where.append("rt.num_votes >= ?")
            rt_params.append(min_votes)
        if max_runtime is not None:
            sc_where.append("(sc.runtime_mins IS NULL OR sc.runtime_mins <= ?)")
            sc_params.append(max_runtime)
            rt_where.append("(rt.runtime_mins IS NULL OR rt.runtime_mins <= ?)")
            rt_params.append(max_runtime)
        if dismissed_ids and len(dismissed_ids) <= 500:
            d_ph = ",".join("?" * len(dismissed_ids))
            sc_where.append(f"sc.imdb_id NOT IN ({d_ph})")
            sc_params.extend(sorted(dismissed_ids))
            # Rated titles are not dismissed (they're in the watchlist), skip filter

        sc_where_clause = " AND ".join(sc_where)
        rt_where_clause = " AND ".join(rt_where)

        union_sql = f"""
            SELECT sc.imdb_id, sc.title, sc.year, sc.title_type,
                   sc.imdb_rating, sc.num_votes, sc.runtime_mins,
                   sc.genres, sc.languages,
                   sc.predicted_score, 0 AS is_rated,
                   GROUP_CONCAT(DISTINCT tp.role) AS roles_csv
            FROM scored_candidates sc
            JOIN title_people tp ON tp.imdb_id = sc.imdb_id
            WHERE {sc_where_clause}
            GROUP BY sc.imdb_id

            UNION ALL

            SELECT rt.imdb_id, rt.title, rt.year, rt.title_type,
                   rt.imdb_rating, rt.num_votes, rt.runtime_mins,
                   rt.genres, rt.languages,
                   rt.user_rating AS predicted_score, 1 AS is_rated,
                   GROUP_CONCAT(DISTINCT tp.role) AS roles_csv
            FROM rated_titles rt
            JOIN title_people tp ON tp.imdb_id = rt.imdb_id
            WHERE {rt_where_clause}
            GROUP BY rt.imdb_id
        """
        all_params = sc_params + rt_params

        count_sql = f"SELECT COUNT(*) FROM ({union_sql})"
        total_row = conn.execute(count_sql, all_params).fetchone()
        total = total_row[0] if total_row else 0

        rows = conn.execute(
            f"SELECT * FROM ({union_sql}) ORDER BY predicted_score DESC LIMIT ?",
            all_params + [limit],
        ).fetchall()
    except sqlite3.OperationalError:
        return 0, []
    finally:
        conn.close()

    large_dismissed = dismissed_ids if dismissed_ids and len(dismissed_ids) > 500 else set()
    result = []
    for row in rows:
        if large_dismissed and row["imdb_id"] in large_dismissed:
            continue
        result.append(dict(row))
    return total, result
```

### Step 4 — `app/models/schemas.py`: add is_rated to PersonTitleResult

In `PersonTitleResult`, add after `roles`:

```python
    is_rated: bool = Field(
        default=False,
        description="True if this title is in the user's rated watchlist.",
    )
```

### Step 5 — `app/api/routes.py`: pass is_rated in titles_by_person

In the `results` list comprehension inside `titles_by_person`, add `is_rated`:

```python
    results = [
        PersonTitleResult(
            imdb_id=row["imdb_id"],
            title=row["title"],
            year=row["year"],
            title_type=row["title_type"],
            imdb_rating=row["imdb_rating"],
            num_votes=row["num_votes"],
            runtime_mins=row["runtime_mins"],
            genres=json.loads(row["genres"]),
            predicted_score=row["predicted_score"],
            languages=json.loads(row["languages"] or "[]"),
            roles=row["roles_csv"].split(",") if row.get("roles_csv") else [],
            is_rated=bool(row["is_rated"]),
        )
        for row in rows
    ]
```

---

## Post-conditions

```bash
python -c "
import sqlite3
db = 'data/cache/scored_candidates.db'
conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cols = [r[1] for r in conn.execute('PRAGMA table_info(rated_titles)').fetchall()]
print('rated_titles columns:', cols)
assert 'genres' in cols, 'genres missing'
assert 'user_rating' in cols, 'user_rating missing'
conn.close()
print('OK')
"
```

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

---

## Files Changed

- `app/services/scored_store.py`
- `app/models/schemas.py`
- `app/api/routes.py`

---

## Commit Message

```
fix: enrich rated_titles table and UNION into person browse query (ST-002)
```
