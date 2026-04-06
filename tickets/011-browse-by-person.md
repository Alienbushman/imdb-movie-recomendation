---
id: "011"
title: "Browse by Director or Actor"
status: open
priority: medium
component: full_stack
files_affected:
  - app/api/routes.py
  - app/models/schemas.py
  - app/services/scored_store.py
  - app/services/pipeline.py
  - frontend/app/pages/person.vue
  - frontend/app/stores/person.ts
  - frontend/app/layouts/default.vue
  - frontend/app/composables/useApi.ts
  - frontend/app/types/index.ts
---

# TICKET-011: Browse by Director or Actor

---

## Summary

Add a "Browse by Person" page where users can search for a director or actor by name and
see the titles by that person from the scored candidates database, ranked by the user's
predicted taste score. This lets users answer: "What's the best Akira Kurosawa film I
haven't seen yet, according to my taste?"

---

## Problem Details

The recommendations page surfaces top-N titles across all directors/actors combined. Users
frequently want to explore a specific filmmaker's or actor's body of work ranked by their
personal taste — for example:

- They've just discovered a director they love and want to know which of their titles to
  watch next
- They want to compare the model's ranking of a prolific actor's filmography against the
  general IMDB rating
- They're deciding whether to invest time in a well-known director's back catalogue

The "Find Similar" feature (ticket 009) finds titles similar to a seed title but doesn't
answer "show me everything by person X, ranked for me." The recommendations page ranks by
overall predicted score but can't filter to a single person. This ticket fills that gap.

---

## Solution

### Architecture

**Backend** adds two new endpoints:

1. **Person search** (`GET /api/v1/people/search`) — Autocomplete endpoint that searches
   for directors/actors/writers by name substring among people who have titles in the
   scored candidates database. Returns lightweight results for typeahead.

2. **Titles by person** (`GET /api/v1/people/{name_id}`) — Given an IMDB name ID (nconst),
   returns all scored titles featuring that person sorted by predicted taste score
   descending. Accepts the same scalar filter parameters as the recommendations endpoints.

**Scored DB extension** — `scored_candidates.db` gains two companion tables populated
during the pipeline's scored-write step:
- `people` (`name_id TEXT PK, name TEXT, primary_profession TEXT`) — one row per unique person
- `title_people` (`imdb_id TEXT, name_id TEXT, role TEXT`) — join table linking titles to people

This keeps GET endpoints fast without re-reading the IMDB TSV files after the pipeline run.

**Frontend** adds:
- A new `/person` page with a person search autocomplete and results grid
- A navigation link in the app bar alongside "Find Similar"
- Results displayed using the existing `RecommendationCard` component
- The existing `FilterDrawer` component reused for scalar filters
- A role toggle (Director / Actor / Any) above the results to narrow by crew role

---

## Subtasks

| # | File | Title | Effort | Depends On |
|---|------|-------|--------|------------|
| 1 | [ST-001-backend-person-search.md](011-browse-by-person/ST-001-backend-person-search.md) | Backend: Person search + DB schema extension | medium | — |
| 2 | [ST-002-backend-titles-by-person.md](011-browse-by-person/ST-002-backend-titles-by-person.md) | Backend: Titles by person endpoint | medium | 1 |
| 3 | [ST-003-frontend-person-page.md](011-browse-by-person/ST-003-frontend-person-page.md) | Frontend: Person browse page with search | medium | 1 |
| 4 | [ST-004-frontend-results-and-filters.md](011-browse-by-person/ST-004-frontend-results-and-filters.md) | Frontend: Results display + role filter | medium | 2, 3 |

---

## Acceptance Criteria

- [ ] A "By Person" link is visible in the app bar, navigating to `/person`
- [ ] The person page has a search bar with autocomplete that queries the backend
- [ ] Selecting a person shows a ranked grid of their titles from the scored candidates DB
- [ ] Results are ranked by predicted taste score (highest first by default)
- [ ] The filter sidebar is available with the same scalar filters as recommendations
- [ ] A role toggle lets users narrow results to "Director", "Actor", or "Any role"
- [ ] Each result card shows the person's role on that title (e.g., "Director", "Actor")
- [ ] Lint passes: `uv run ruff check app/` and `cd frontend && npx nuxt typecheck`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`

---

## Non-Goals

- No ML-based person similarity — ranking uses the existing predicted score, not a new model
- No "browse multiple people simultaneously" — single person only for V1
- No TMDB/OMDb enrichment of person data — uses only IMDB dataset fields
- No biography or complete filmography — only titles present in the scored candidates pool
- No infinite scroll or server-side pagination — top-N in one response (same as recommendations)
