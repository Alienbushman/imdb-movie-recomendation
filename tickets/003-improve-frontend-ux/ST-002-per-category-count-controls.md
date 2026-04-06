---
ticket: "003"
subtask: 2
title: "Per-Category Result Count Controls"
status: done
effort: low-medium
component: full_stack
depends_on: []
files_modified:
  - app/api/routes.py
  - app/models/schemas.py
  - app/services/recommend.py
  - frontend/app/stores/filters.ts
  - frontend/app/pages/index.vue
  - frontend/app/composables/useApi.ts
  - frontend/app/types/index.ts
files_created: []
---

# SUBTASK 02: Per-Category Result Count Controls

---

## Objective

Allow users to control how many recommendations they see per category (movies, series, animation) from the UI, instead of being locked to the hardcoded `config.yaml` defaults (20 movies, 10 series, 10 animation).

## Context

Currently `top_n` per category is set in `config.yaml` under `recommendations`:
```yaml
recommendations:
  top_n_movies: 20
  top_n_series: 10
  top_n_animation: 10
```

These values are read in `recommend.py:build_recommendations_from_scored()` at lines 297-299:
```python
max_movies = rec_cfg.top_n_movies
max_series = rec_cfg.top_n_series
max_animation = rec_cfg.top_n_animation
```

There is no API parameter to override these, and no UI control. A user who only watches movies might want 50 movies and 0 series, while an anime fan might want 30 animation results.

## Implementation

### 1. Backend: Add `top_n` parameters to `RecommendationFilters`

In `app/models/schemas.py`, add three optional fields to `RecommendationFilters`:

```python
top_n_movies: int | None = Field(
    default=None,
    description="Override number of movie recommendations to return (default: config value).",
    ge=0,
    le=100,
)
top_n_series: int | None = Field(
    default=None,
    description="Override number of series recommendations to return (default: config value).",
    ge=0,
    le=100,
)
top_n_animation: int | None = Field(
    default=None,
    description="Override number of animation recommendations to return (default: config value).",
    ge=0,
    le=100,
)
```

### 2. Backend: Wire through API routes

Add `top_n_movies`, `top_n_series`, `top_n_animation` as optional `Query` parameters to:
- `POST /recommendations`
- `POST /recommendations/filter`

Pass them through `_build_filters()` into the `RecommendationFilters` object.

### 3. Backend: Apply overrides in `recommend.py`

In `build_recommendations_from_scored()`, replace the hardcoded config reads:

```python
max_movies = (filters.top_n_movies if filters and filters.top_n_movies is not None
              else rec_cfg.top_n_movies)
max_series = (filters.top_n_series if filters and filters.top_n_series is not None
              else rec_cfg.top_n_series)
max_animation = (filters.top_n_animation if filters and filters.top_n_animation is not None
                 else rec_cfg.top_n_animation)
```

### 4. Frontend: Add count controls to filter state

In `stores/filters.ts`, add:
```typescript
const topNMovies = ref<number | undefined>()
const topNSeries = ref<number | undefined>()
const topNAnimation = ref<number | undefined>()
```

Include them in `buildFilters()` and `resetFilters()`.

### 5. Frontend: Add UI controls

In the filter panel (or near the category tabs), add number inputs for each category:

```vue
<v-number-input
  v-model="filters.topNMovies"
  label="Movies"
  :min="0"
  :max="100"
  :step="5"
  density="compact"
  hide-details
  control-variant="stacked"
/>
```

These could appear:
- **Option A:** In the filter panel under a "Content Type" or "Results" section
- **Option B:** Inline next to each tab header (small stepper)
- **Option C:** In a popover triggered by clicking the count badge on each tab

Recommendation: **Option A** for simplicity, grouped under a "Results" heading in the filter panel.

### 6. Frontend: Update API composable

In `useApi.ts`, pass the new params through `getRecommendations()` and `filterRecommendations()`:
```typescript
if (filters.top_n_movies != null) query.top_n_movies = filters.top_n_movies
if (filters.top_n_series != null) query.top_n_series = filters.top_n_series
if (filters.top_n_animation != null) query.top_n_animation = filters.top_n_animation
```

### 7. Frontend: Update types

In `types/index.ts`, add to `RecommendationFilters`:
```typescript
top_n_movies?: number | null
top_n_series?: number | null
top_n_animation?: number | null
```

## Acceptance Criteria

- [x] API accepts `top_n_movies`, `top_n_series`, `top_n_animation` as optional query params on `/recommendations` and `/recommendations/filter`
- [x] Backend uses overrides when provided, falls back to `config.yaml` defaults when not
- [x] Frontend provides number inputs for each category count
- [x] Setting a category count to `0` hides that category entirely
- [x] Default values match current `config.yaml` (20, 10, 10)
- [x] Counts are included in the active filter summary when non-default

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
