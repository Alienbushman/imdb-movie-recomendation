---
id: "009"
title: "Find Similar Movies"
status: done
priority: medium
component: full_stack
files_affected:
  - app/api/routes.py
  - app/services/scored_store.py
  - app/services/similar.py
  - app/models/schemas.py
  - frontend/app/pages/similar.vue
  - frontend/app/layouts/default.vue
  - frontend/app/composables/useApi.ts
  - frontend/app/types/index.ts
  - frontend/app/stores/filters.ts
  - frontend/app/components/FilterDrawer.vue
---

# TICKET-009: Find Similar Movies

---

## Summary

Add a dedicated "Find Similar" page where users can type in a movie or series title, select it from autocomplete results, and see a ranked list of similar titles from the scored candidates database. Results should be filterable using the same sidebar filter panel as the recommendations page, plus a seen/unseen toggle that lets users filter by whether they've already rated a title.

---

## Problem Details

The current app is great at recommending titles based on overall taste, but doesn't support a common discovery workflow: "I loved Movie X — what else is like it?" The `similar_to` field on recommendations shows a few titles from the user's watchlist that share genres, but there's no way to go the other direction: pick a title and find everything similar to it in the database.

Users need:
- A way to search for any title (from both their rated titles and the scored candidates pool)
- A ranked list of similar titles based on meaningful similarity signals (genre overlap, shared directors/actors, language, era)
- The same filtering controls they're used to on the recommendations page (year range, genre include/exclude, language, IMDB rating, runtime, vote count)
- A way to distinguish "already seen" vs "unseen" titles — some users want only new discoveries, others want to verify that the similarity engine returns titles they already know they like

---

## Solution

### Architecture

**Backend** adds two new endpoints:

1. **Title search** (`GET /api/v1/search`) — Autocomplete endpoint that searches the scored candidates DB + the user's rated titles by title substring. Returns lightweight results for the frontend typeahead.

2. **Find similar** (`GET /api/v1/similar/{imdb_id}`) — Given a seed title's IMDB ID, computes a similarity score for every candidate in the scored DB and returns the top-N most similar, subject to the same filter parameters used by recommendations. Includes a `is_rated` boolean field so the frontend can toggle seen/unseen.

**Similarity scoring** uses a weighted combination of:
- **Genre Jaccard similarity** (weight: 0.4) — intersection-over-union of genre sets
- **Shared director** (weight: 0.2) — binary: does any director match?
- **Shared actors** (weight: 0.15) — fraction of shared actors (top 3)
- **Language match** (weight: 0.1) — binary: same original language?
- **Era proximity** (weight: 0.1) — `1 - |year_diff| / 50`, clamped to [0, 1]
- **IMDB rating proximity** (weight: 0.05) — `1 - |rating_diff| / 10`

This is a content-based similarity — it doesn't use the ML model's predicted scores. Predicted score is still available as a sort/filter option on the results.

**Frontend** adds:
- A new `/similar` page with a search bar (Vuetify `v-autocomplete`) and results grid
- Navigation link in the app bar
- The existing `FilterDrawer` component is reused on the similar page, with an added "Seen/Unseen" toggle
- Results are displayed using the existing `RecommendationCard` component (the `Recommendation` schema is reused with the addition of a `similarity_score` and `is_rated` field on the similar-specific response)

---

## Subtasks

| # | File | Title | Effort | Depends On |
|---|------|-------|--------|------------|
| 1 | [ST-001-backend-title-search.md](009-find-similar-movies/ST-001-backend-title-search.md) | Backend: Title search endpoint | low | — |
| 2 | [ST-002-backend-similarity-engine.md](009-find-similar-movies/ST-002-backend-similarity-engine.md) | Backend: Similarity engine + API endpoint | medium | 1 |
| 3 | [ST-003-frontend-similar-page.md](009-find-similar-movies/ST-003-frontend-similar-page.md) | Frontend: Similar page with search + routing | medium | 1 |
| 4 | [ST-004-frontend-results-and-filters.md](009-find-similar-movies/ST-004-frontend-results-and-filters.md) | Frontend: Results display + seen/unseen filter | medium | 2, 3 |

---

## Acceptance Criteria

- [ ] A "Find Similar" link is visible in the app bar, navigating to `/similar`
- [ ] The similar page has a search bar with autocomplete that queries the backend
- [ ] Selecting a title shows a ranked grid of similar titles from the scored candidates DB
- [ ] Similarity is computed using genre overlap, shared crew, language, and era proximity
- [ ] The filter sidebar is available on the similar page with the same controls as recommendations
- [ ] A seen/unseen toggle lets users filter results by whether they've rated the title
- [ ] Results display using the same card component as recommendations
- [ ] Each result shows a similarity score and explanation of why it's similar
- [ ] Lint passes: `uv run ruff check app/` and `cd frontend && npx nuxt typecheck`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`

---

## Non-Goals

- No ML-based similarity (e.g., embedding distance) — content-based Jaccard + crew overlap is sufficient for V1
- No "similar to multiple titles" (playlist-style) — single seed title only
- No TMDB/OMDb enrichment for similarity — uses only data already in the scored candidates DB
- No infinite scroll or server-side pagination — top-N results returned in a single response (same pattern as recommendations)
