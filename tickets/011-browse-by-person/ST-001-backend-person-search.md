---
ticket: "011"
subtask: 1
title: "Backend: Person Search + DB Schema Extension"
status: open
effort: medium
component: backend
depends_on: []
files_modified:
  - app/services/scored_store.py
  - app/services/pipeline.py
  - app/api/routes.py
  - app/models/schemas.py
files_created: []
---

# SUBTASK 01: Backend — Person Search + DB Schema Extension

---

## Objective

Extend `scored_candidates.db` with person tables populated during the pipeline write step,
and add a `GET /api/v1/people/search` autocomplete endpoint that searches directors, actors,
and other crew by name.

## Pre-conditions

Read these files in full before writing any code:
- `app/services/scored_store.py` — understand the existing schema and write methods
- `app/services/pipeline.py` — understand where scored candidates are written
- `app/services/candidates.py` — find how `name_lookup` is built and what crew fields
  `CandidateTitle` carries (exact field names for directors, cast, etc.)

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

Both must pass before starting.

## Context

After a pipeline run, `_state` holds only the model and rated titles — the full candidates
collection and `name_lookup` dict are not retained. To keep GET endpoints fast, person data
must be persisted to SQLite during the same write step that stores scored candidates.

The `scored_candidates.db` already has a `scored_candidates` table. This subtask adds two
companion tables to the same database file using the same connection helper.

## Implementation

### 1. Add `people` and `title_people` tables to `scored_store.py`

In the `_create_tables()` (or equivalent initialisation) function, add:

```sql
CREATE TABLE IF NOT EXISTS people (
    name_id TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    primary_profession TEXT
);

CREATE TABLE IF NOT EXISTS title_people (
    imdb_id TEXT NOT NULL,
    name_id TEXT NOT NULL,
    role    TEXT NOT NULL,          -- e.g. "director", "actor", "writer"
    PRIMARY KEY (imdb_id, name_id, role)
);

CREATE INDEX IF NOT EXISTS idx_title_people_name_id ON title_people (name_id);
CREATE INDEX IF NOT EXISTS idx_title_people_imdb_id ON title_people (imdb_id);
```

Add these DDL statements alongside the existing table creation so they run on every startup
(the `IF NOT EXISTS` guard makes this safe).

### 2. Add `write_people()` to `scored_store.py`

```python
def write_people(
    people: list[dict],         # [{name_id, name, primary_profession}]
    title_people: list[dict],   # [{imdb_id, name_id, role}]
) -> None:
    """Persist person and title-person rows to the scored DB.

    Replaces existing rows (INSERT OR REPLACE) so re-running the pipeline
    produces a clean slate without requiring a manual DB delete.
    """
```

Use `INSERT OR REPLACE INTO people` and `INSERT OR REPLACE INTO title_people`.
Batch the inserts (`executemany`) for performance — there can be hundreds of thousands
of title_people rows.

### 3. Extend the pipeline write step in `pipeline.py`

After reading `candidates.py` to confirm the exact field names, extend the step that calls
`scored_store.write_scored()` (or wherever scored candidates are persisted) to also call
`scored_store.write_people()`.

Extract person rows from each `CandidateTitle` before it is written to the DB. The exact
fields depend on what `candidates.py` attaches — read the code. Common pattern:

```python
people_map: dict[str, dict] = {}     # name_id → {name, primary_profession}
title_people_rows: list[dict] = []

for candidate in scored_candidates:
    # Directors, writers, etc. — check the actual CandidateTitle field names
    for role, name_ids in [
        ("director", candidate.director_ids or []),
        ("actor",    candidate.cast_ids or []),
        ("writer",   candidate.writer_ids or []),
    ]:
        for name_id in name_ids:
            if name_id in name_lookup:
                person = name_lookup[name_id]
                people_map[name_id] = {
                    "name_id": name_id,
                    "name": person.name,
                    "primary_profession": person.primary_profession,
                }
                title_people_rows.append({
                    "imdb_id": candidate.imdb_id,
                    "name_id": name_id,
                    "role": role,
                })

scored_store.write_people(list(people_map.values()), title_people_rows)
```

`name_lookup` is already in scope during the pipeline run — confirm this by reading
`pipeline.py` and `candidates.py`.

### 4. Add `PersonSearchResult` schema to `schemas.py`

```python
class PersonSearchResult(BaseModel):
    """Lightweight person info for search autocomplete."""
    name_id: str
    name: str
    primary_profession: str | None = None
    title_count: int = Field(
        description="Number of scored titles featuring this person."
    )
```

### 5. Add `search_people()` to `scored_store.py`

```python
def search_people(query: str, limit: int = 20) -> list[dict]:
    """Search people by name substring (case-insensitive).

    Returns dicts with keys: name_id, name, primary_profession, title_count.
    Only returns people who have at least one row in title_people.
    """
```

```sql
SELECT p.name_id, p.name, p.primary_profession,
       COUNT(DISTINCT tp.imdb_id) AS title_count
FROM   people p
JOIN   title_people tp ON tp.name_id = p.name_id
WHERE  p.name LIKE ? COLLATE NOCASE
GROUP  BY p.name_id
ORDER  BY title_count DESC
LIMIT  ?
```

Bind `f"%{query}%"` and `limit`.

### 6. Add `GET /api/v1/people/search` route

```python
@router.get(
    "/people/search",
    response_model=list[PersonSearchResult],
    summary="Search for a director or actor by name",
    tags=["Person Browse"],
)
def search_people_endpoint(
    q: str = Query(..., min_length=2, description="Name search query (min 2 characters)"),
    limit: int = Query(20, ge=1, le=50),
):
    """Return people (directors/actors/writers) whose name contains the query string."""
    if not _db_ready():
        return []
    rows = scored_store.search_people(q, limit)
    return [PersonSearchResult(**r) for r in rows]
```

`_db_ready()` should be whatever guard the existing routes use to check the pipeline has
been run (read `routes.py` to see the existing pattern).

## Acceptance Criteria

- [ ] `people` and `title_people` tables exist in `scored_candidates.db` after a pipeline run
- [ ] `GET /api/v1/people/search?q=kuro` returns matching people with `title_count`
- [ ] Results only include people who have titles in the scored DB
- [ ] Minimum query length of 2 is enforced (422 for shorter)
- [ ] Returns empty list (not error) when no matches found
- [ ] Re-running the pipeline replaces person rows cleanly (no duplicates)
- [ ] `uv run ruff check app/` passes
- [ ] `uv run pytest tests/ -q` passes

## Commit Message

```
feat: extend scored DB with people tables and add person search endpoint
```
