---
ticket: "004"
subtask: 3
title: "Rename Animation to Anime in Frontend"
status: done
effort: low
component: frontend
depends_on: [2]
files_modified:
  - frontend/app/types/index.ts
  - frontend/app/stores/recommendations.ts
  - frontend/app/composables/useApi.ts
  - frontend/app/pages/index.vue
files_created: []
---

# SUBTASK 004-03: Rename Animation → Anime in Frontend

---

## Context

After subtask 02, the API returns `anime` instead of `animation` and the endpoint is `/recommendations/anime`. The frontend needs to catch up: type definitions, store state, API calls, and UI labels all still say "animation".

---

## Implementation

### 1. `frontend/app/types/index.ts`

Update the `RecommendationResponse` type:

```ts
// Before:
animation: Recommendation[]
// After:
anime: Recommendation[]
```

Update `RecommendationFilters` (if defined here):

```ts
// Before:
top_n_animation?: number
// After:
top_n_anime?: number
```

### 2. `frontend/app/stores/recommendations.ts`

- Rename any state property `animation` → `anime`
- Rename any getter or computed that references `response.animation` → `response.anime`
- Update log/debug strings if any reference "animation"

### 3. `frontend/app/composables/useApi.ts`

- Update the endpoint call from `/recommendations/animation` → `/recommendations/anime`
- Update the query parameter name `top_n_animation` → `top_n_anime` if passed

### 4. `frontend/app/pages/index.vue`

- Update the tab/section label from "Animation" → "Anime"
- Update any `v-bind`, `v-model`, or template references from `animation` → `anime`
- Update any display copy that says "animation" in a user-visible context

### 5. `frontend/app/stores/filters.ts` (if applicable)

Check whether `top_n_animation` is referenced here and rename to `top_n_anime`.

---

## Acceptance Criteria

- [x] The frontend tab/section label displays "Anime" (not "Animation")
- [x] The frontend calls `/api/v1/recommendations/anime` (not `/recommendations/animation`)
- [x] TypeScript types use `anime` not `animation` in response and filter interfaces
- [x] `cd frontend && npx nuxt typecheck` passes with no new errors
