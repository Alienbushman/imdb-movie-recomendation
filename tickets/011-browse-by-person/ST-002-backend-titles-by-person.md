---
ticket: "011"
subtask: 2
title: "Backend: Titles by Person Endpoint"
status: open
effort: medium
component: backend
depends_on: [1]
files_modified:
  - app/api/routes.py
  - app/models/schemas.py
  - app/services/scored_store.py
files_created: []
---

# SUBTASK 02: Backend — Titles by Person Endpoint

---

## Objective

Add a `GET /api/v1/people/{name_id}` endpoint that returns all scored titles featuring a
given person, ranked by predicted taste score and filtered by the same scalar parameters
used by the recommendations endpoints.

## Pre-conditions

- ST-001 is `Done`: `people` and `title_people` tables exist and are populated
- Verify: `SELECT COUNT(*) FROM title_people;` in `scored_candidates.db` returns > 0

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

## Context

The recommendations endpoints (`GET /recommendations/movies` etc.) filter `scored_candidates`
using scalar SQL filters defined in `scored_store.query_candidates()`. The person endpoint
reuses that same filter logic but adds a JOIN on `title_people` to restrict results to a
specific person.

The response reuses the existing `Recommendation` schema wherever possible. Each result
needs one extra field — the role(s) the person played on that title — so a lightweight
wrapper or an extended schema is needed.

## Implementation

### 1. Add `PersonTitleResult` schema to `schemas.py`

```python
class PersonTitleResult(BaseModel):
    """A scored title from the Browse by Person results."""
    # Reuse all Recommendation fields via inheritance or composition
    imdb_id: str
    title: str
    year: int | None = None
    title_type: str
    imdb_rating: float | None = None
    num_votes: int | None = None
    runtime_minutes: int | None = None
    genres: list[str] = []
    predicted_score: float
    explanation: list[str] = []
    similar_to: list[str] = []
    languages: list[str] = []
    roles: list[str] = Field(
        description="The roles this person played on the title (e.g. ['director', 'writer'])."
    )

class PersonTitlesResponse(BaseModel):
    name_id: str
    name: str
    primary_profession: str | None = None
    total: int = Field(description="Total matching titles before limit is applied.")
    results: list[PersonTitleResult]
```

### 2. Add `query_titles_by_person()` to `scored_store.py`

Read the existing `query_candidates()` function carefully before writing this — the goal is
to reuse the same scalar filter logic (year, rating, runtime, votes, dismissed exclusion)
with an additional JOIN condition.

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
    """Return (total_count, rows) for scored titles featuring name_id.

    Rows include all scored_candidates columns plus an aggregated `roles` list.
    Results are ordered by predicted_score DESC.
    """
```

Core SQL pattern:

```sql
SELECT sc.*, GROUP_CONCAT(DISTINCT tp.role) AS roles_csv,
       COUNT(*) OVER () AS total_count
FROM   scored_candidates sc
JOIN   title_people tp ON tp.imdb_id = sc.imdb_id
WHERE  tp.name_id = ?
  AND  sc.imdb_id NOT IN (/* dismissed_ids */)
  -- scalar filters applied here (same pattern as query_candidates)
GROUP  BY sc.imdb_id
ORDER  BY sc.predicted_score DESC
LIMIT  ?
```

Split `roles_csv` on `,` in Python to produce `roles: list[str]`.

Return `(total, rows)` where `total` is the unfiltered count for that person (before
applying the LIMIT).

### 3. Add `GET /api/v1/people/{name_id}` route

```python
@router.get(
    "/people/{name_id}",
    response_model=PersonTitlesResponse,
    summary="Get top-scored titles featuring a director or actor",
    tags=["Person Browse"],
)
def titles_by_person(
    name_id: str,
    limit: int = Query(100, ge=1, le=500),
    min_year: int | None = Query(None),
    max_year: int | None = Query(None),
    min_rating: float | None = Query(None),
    min_votes: int | None = Query(None),
    max_runtime: int | None = Query(None),
):
    """Return scored titles featuring the given IMDB name ID, ranked by predicted score."""
    if not _db_ready():
        raise HTTPException(status_code=503, detail="Pipeline has not been run yet.")

    # Resolve person metadata
    person = scored_store.get_person(name_id)
    if person is None:
        raise HTTPException(status_code=404, detail=f"Person {name_id!r} not found.")

    dismissed = set(dismissed_store.load())
    total, rows = scored_store.query_titles_by_person(
        name_id=name_id,
        limit=limit,
        min_year=min_year,
        max_year=max_year,
        min_rating=min_rating,
        min_votes=min_votes,
        max_runtime=max_runtime,
        dismissed_ids=dismissed,
    )

    results = [
        PersonTitleResult(
            **{k: v for k, v in row.items() if k != "roles_csv"},
            roles=row["roles_csv"].split(",") if row.get("roles_csv") else [],
        )
        for row in rows
    ]
    return PersonTitlesResponse(
        name_id=person["name_id"],
        name=person["name"],
        primary_profession=person.get("primary_profession"),
        total=total,
        results=results,
    )
```

Add a helper `get_person(name_id)` to `scored_store.py`:

```python
def get_person(name_id: str) -> dict | None:
    """Return the people row for name_id, or None if not found."""
```

## Acceptance Criteria

- [ ] `GET /api/v1/people/{name_id}` returns `PersonTitlesResponse` for a valid name_id
- [ ] Results are ordered by `predicted_score` descending
- [ ] Each result includes a `roles` list (e.g. `["director", "writer"]`)
- [ ] Scalar filters (min_year, max_year, min_rating, min_votes, max_runtime) are applied
- [ ] Dismissed titles are excluded from results
- [ ] Returns 404 for unknown name_id
- [ ] Returns 503 if pipeline has not been run
- [ ] `uv run ruff check app/` passes
- [ ] `uv run pytest tests/ -q` passes

## Commit Message

```
feat: add GET /people/{name_id} endpoint for browsing titles by person
```
