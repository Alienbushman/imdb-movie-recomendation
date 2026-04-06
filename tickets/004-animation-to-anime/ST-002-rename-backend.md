---
ticket: "004"
subtask: 2
title: "Rename Animation to Anime in Config and Backend"
status: done
effort: low
component: backend
depends_on: [1]
files_modified:
  - config.yaml
  - app/core/config.py
  - app/models/schemas.py
  - app/services/recommend.py
  - app/api/routes.py
files_created: []
---

# SUBTASK 004-02: Rename Animation → Anime in Config and Backend

---

## Context

With `CandidateTitle.is_anime` in place, rename every "animation" reference in the backend so the API surface, config, and internal logic all consistently say "anime".

---

## Implementation

### 1. `config.yaml`

```yaml
recommendations:
  top_n_movies: 20
  top_n_series: 10
  top_n_anime: 10            # was: top_n_animation

categories:
  movie:
    title_types: ["movie", "tvMovie"]
    label: "Movies"
  series:
    title_types: ["tvSeries", "tvMiniSeries"]
    label: "Series"
  anime:                     # was: animation
    title_types: ["movie", "tvSeries", "tvMiniSeries"]
    label: "Anime"           # was: "Animation"
```

### 2. `app/core/config.py`

Check the `RecommendationConfig` (or equivalent Pydantic settings model) for a `top_n_animation` field and rename it to `top_n_anime`. Verify the `categories` config key is read dynamically (via `cat_cfg.get("anime", ...)`) so no further change is needed there.

### 3. `app/models/schemas.py`

**`RecommendationResponse`** — rename field:
```python
anime: list[Recommendation] = Field(
    default=[],
    description="Ranked anime recommendations (Japanese animation), sorted by predicted score.",
)
# Remove: animation field
```

**`RecommendationFilters`** — rename field:
```python
top_n_anime: int | None = Field(
    default=None,
    description="Override number of anime recommendations to return (default: config value).",
    ge=0,
    le=100,
)
# Remove: top_n_animation field
```

### 4. `app/services/recommend.py`

In `build_recommendations_from_scored()`:

- `animation: list[Recommendation] = []` → `anime: list[Recommendation] = []`
- `max_animation` → `max_anime`
- `filters.top_n_animation` → `filters.top_n_anime`
- `rec_cfg.top_n_animation` → `rec_cfg.top_n_anime`
- Categorization condition (currently line 344):
  ```python
  # Before:
  is_animation = "Animation" in candidate.genres
  if is_animation and len(animation) < max_animation:
      animation.append(rec)
  # After:
  if candidate.is_anime and len(anime) < max_anime:
      anime.append(rec)
  ```
- `cat_cfg.get("animation", ...)` → `cat_cfg.get("anime", ...)`
- Early termination condition: `len(animation) >= max_animation` → `len(anime) >= max_anime`
- Logger message: `"%d animation"` → `"%d anime"`
- `RecommendationResponse(animation=animation, ...)` → `RecommendationResponse(anime=anime, ...)`

### 5. `app/api/routes.py`

- Rename endpoint path: `/recommendations/animation` → `/recommendations/anime`
- Rename any query param `top_n_animation` → `top_n_anime`
- Update `response.animation` → `response.anime` in any route that accesses the field directly

---

## Acceptance Criteria

- [x] `GET /api/v1/recommendations/anime` is the active endpoint; `/recommendations/animation` is removed
- [x] `RecommendationResponse.anime` exists; `.animation` does not
- [x] `RecommendationFilters.top_n_anime` exists; `top_n_animation` does not
- [x] `config.yaml` uses `top_n_anime` and `categories.anime`
- [x] Categorization in `recommend.py` uses `candidate.is_anime` (not a genre string check)
- [x] `uv run ruff check app/` passes
- [x] `uv run pytest tests/ -q` passes
