---
ticket: "009"
subtask: 1
title: "Backend: Title Search Endpoint"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/api/routes.py
  - app/models/schemas.py
  - app/services/scored_store.py
files_created: []
---

# SUBTASK 01: Backend — Title Search Endpoint

---

## Objective

Add a `GET /api/v1/search` endpoint that searches for titles by name, returning lightweight results suitable for a frontend autocomplete/typeahead input.

## Context

The "Find Similar" feature needs users to first select a seed title. The frontend will use an autocomplete component that queries this endpoint as the user types. The search should cover both:
1. Titles in the `scored_candidates` SQLite DB (the full pool of unseen candidates)
2. Titles from the user's rated watchlist (so users can search for movies they've already seen)

The user's rated titles are held in `_state.rated_titles` after a pipeline run. If the pipeline hasn't been run yet, the search falls back to scored candidates only.

## Implementation

### 1. Add `TitleSearchResult` schema to `schemas.py`

```python
class TitleSearchResult(BaseModel):
    """Lightweight title info for search autocomplete."""
    imdb_id: str
    title: str
    year: int | None = None
    title_type: str
    is_rated: bool = Field(
        default=False,
        description="True if this title is in the user's rated watchlist.",
    )
```

### 2. Add `search_titles()` to `scored_store.py`

```python
def search_titles(query: str, limit: int = 20) -> list[dict]:
    """Search scored_candidates by title substring (case-insensitive).

    Returns dicts with keys: imdb_id, title, year, title_type.
    """
```

- Use `WHERE title LIKE ? COLLATE NOCASE` with `%query%`
- Order by `num_votes DESC` (most popular matches first) to give better autocomplete results
- Limit to `limit` rows
- Return raw dicts, not full `CandidateTitle` objects (keep it lightweight)

### 3. Add `GET /api/v1/search` route

```python
@router.get(
    "/search",
    response_model=list[TitleSearchResult],
    summary="Search titles by name",
    tags=["Similar"],
)
def search_titles_endpoint(
    q: str = Query(..., min_length=2, description="Search query (minimum 2 characters)"),
    limit: int = Query(20, ge=1, le=50, description="Max results to return"),
):
```

- Query `scored_store.search_titles(q, limit)` for candidates
- Also search `_state.rated_titles` by title substring (if pipeline has been run)
- Merge results: rated titles marked with `is_rated=True`, candidates with `is_rated=False`
- Deduplicate by `imdb_id` (rated version wins if both match)
- Sort by: rated titles first, then by title length (shorter = more relevant), limited to `limit`

## Acceptance Criteria

- [ ] `GET /api/v1/search?q=inception` returns matching titles from scored DB
- [ ] Results include titles from the user's rated watchlist (marked `is_rated=True`)
- [ ] Results are deduplicated by IMDB ID
- [ ] Results are ordered by relevance (rated first, then by vote count)
- [ ] Minimum query length of 2 characters is enforced
- [ ] Returns empty list (not error) when no matches found
- [ ] `uv run ruff check app/` passes
