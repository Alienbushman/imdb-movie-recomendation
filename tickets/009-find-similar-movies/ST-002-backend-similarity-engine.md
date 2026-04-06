---
ticket: "009"
subtask: 2
title: "Backend: Similarity Engine + API Endpoint"
status: done
effort: medium
component: backend
depends_on: [1]
files_modified:
  - app/api/routes.py
  - app/models/schemas.py
  - app/services/scored_store.py
files_created:
  - app/services/similar.py
---

# SUBTASK 02: Backend — Similarity Engine + API Endpoint

---

## Objective

Create a similarity scoring service and a `GET /api/v1/similar/{imdb_id}` endpoint that returns titles most similar to a given seed title, with filter support and a `is_rated` flag.

## Context

The scored candidates DB contains all candidate titles with their metadata (genres, directors, actors, language, year, etc.). We can compute content-based similarity between any two titles using this metadata. The seed title can come from either the scored DB or the user's rated titles.

The existing `_find_similar_rated()` function in `recommend.py` uses Jaccard similarity on genres — this new service extends that idea with additional signals and applies it across the full candidate pool rather than just the user's rated titles.

## Implementation

### 1. Create `app/services/similar.py`

```python
def compute_similarity(seed: SeedTitle, candidate: CandidateRow) -> float:
    """Compute weighted similarity score between seed and candidate.

    Components:
    - Genre Jaccard (0.4): |intersection| / |union| of genre sets
    - Shared director (0.2): 1.0 if any director overlaps, else 0.0
    - Shared actors (0.15): count of shared actors / max(3, seed actor count)
    - Language match (0.1): 1.0 if same language, else 0.0
    - Era proximity (0.1): max(0, 1 - |year_diff| / 50)
    - Rating proximity (0.05): max(0, 1 - |rating_diff| / 10)

    Returns a float in [0.0, 1.0].
    """
```

```python
def explain_similarity(seed: SeedTitle, candidate: CandidateRow) -> list[str]:
    """Generate human-readable explanations for why these titles are similar.

    Examples:
    - "Shares genres: Action, Sci-Fi"
    - "Same director: Christopher Nolan"
    - "Features shared actor: Leonardo DiCaprio"
    - "Both in English"
    - "Released within 3 years of each other"
    """
```

```python
def find_similar(
    imdb_id: str,
    filters: RecommendationFilters | None,
    top_n: int,
    include_rated: bool | None,  # None = all, True = only rated, False = only unrated
) -> SimilarResponse:
    """Find titles most similar to the given seed.

    1. Look up seed title from scored DB or rated titles
    2. Query all candidates from scored DB (applying SQL-level filters)
    3. Score each candidate against seed
    4. Sort by similarity score desc
    5. Apply seen/unseen filter if specified
    6. Return top-N with explanations
    """
```

### 2. Add schemas to `schemas.py`

```python
class SimilarTitle(BaseModel):
    """A title similar to the seed, with similarity details."""
    title: str
    title_type: str
    year: int | None
    genres: list[str]
    imdb_rating: float | None
    predicted_score: float | None  # from scored DB, if available
    similarity_score: float  # 0.0 to 1.0
    similarity_explanation: list[str]  # why it's similar
    actors: list[str] = []
    director: str | None = None
    language: str | None = None
    imdb_id: str | None = None
    imdb_url: str | None = None
    num_votes: int = 0
    country_code: str | None = None
    is_rated: bool = False  # whether user has rated this title

class SimilarResponse(BaseModel):
    """Response from the find-similar endpoint."""
    seed_title: str
    seed_imdb_id: str
    results: list[SimilarTitle]
    total_candidates: int  # how many were considered before top-N
```

### 3. Add `query_all_candidates_lightweight()` to `scored_store.py`

The existing `query_candidates()` enforces top-N limits and dismissed filtering, which doesn't apply here. Add a new query function:

```python
def query_all_candidates_lightweight(
    filters: RecommendationFilters | None,
) -> list[sqlite3.Row]:
    """Query all scored candidates with optional filters, returning raw rows.

    Unlike query_candidates(), this returns all matching rows without top-N
    limits or dismissed filtering. Used by the similarity engine which needs
    the full pool to rank by similarity score.
    """
```

- Apply the same SQL-level filters as `query_candidates()` (year, language, rating, runtime, vote count, country)
- Genre include/exclude filters applied in Python (same pattern)
- Return raw `sqlite3.Row` objects to avoid constructing full `CandidateTitle` objects for thousands of rows
- Order by `num_votes DESC` as a tiebreaker

### 4. Add `GET /api/v1/similar/{imdb_id}` route

```python
@router.get(
    "/similar/{imdb_id}",
    response_model=SimilarResponse,
    summary="Find titles similar to a given title",
    tags=["Similar"],
)
def get_similar_titles(
    imdb_id: str = Path(description="IMDB ID of the seed title", pattern=r"^tt\d+$"),
    filters: FilterDeps,
    top_n: int = Query(50, ge=1, le=200, description="Max similar titles to return"),
    seen: bool | None = Query(
        None,
        description="Filter by seen status: true=only rated, false=only unrated, null=all",
    ),
):
```

- Call `find_similar(imdb_id, filters, top_n, seen)`
- Return 404 if seed title not found in either scored DB or rated titles
- Return 409 if scored DB is empty (pipeline hasn't been run)

## Acceptance Criteria

- [ ] `GET /api/v1/similar/tt1375666` returns titles similar to Inception
- [ ] Similarity score is a float in [0.0, 1.0] based on genre, crew, language, era
- [ ] Each result includes `similarity_explanation` with human-readable reasons
- [ ] Each result includes `is_rated` flag indicating if user has rated it
- [ ] Filter parameters (year, genre, language, rating, runtime, votes) are respected
- [ ] `seen` query param filters by rated/unrated status
- [ ] Returns 404 when seed title IMDB ID is not found
- [ ] Returns 409 when scored DB has no results
- [ ] `uv run ruff check app/` passes
- [ ] `uv run pytest tests/ -q` passes
