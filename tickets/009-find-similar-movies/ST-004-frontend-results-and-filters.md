---
ticket: "009"
subtask: 4
title: "Frontend: Results Display + Seen/Unseen Filter"
status: done
effort: medium
component: frontend
depends_on: [2, 3]
files_modified:
  - frontend/app/pages/similar.vue
  - frontend/app/stores/similar.ts
  - frontend/app/stores/filters.ts
  - frontend/app/components/FilterDrawer.vue
  - frontend/app/components/RecommendationCard.vue
files_created: []
---

# SUBTASK 04: Frontend — Results Display + Seen/Unseen Filter

---

## Objective

Wire the similar results into the card grid, add a seen/unseen toggle to the filter sidebar, and adapt the card component to display similarity information.

## Context

After subtasks 2 and 3, the backend returns `SimilarResponse` with `SimilarTitle` objects and the frontend page skeleton is in place. This subtask connects the two: displaying results in a grid, adding the seen/unseen filter, and showing similarity-specific information on the cards.

The `RecommendationCard` component currently displays `Recommendation` objects. `SimilarTitle` shares most of the same fields but has `similarity_score` and `similarity_explanation` instead of `predicted_score` and `explanation`, plus the `is_rated` flag. The card needs to handle both schemas.

## Implementation

### 1. Adapt `RecommendationCard.vue` for dual use

The card should accept either a `Recommendation` or a `SimilarTitle` via props. Approach:

- Change the prop type to accept a union type or use a more generic interface
- When `similarity_score` is present, show it as a percentage badge (e.g., "87% match") instead of the predicted score
- When `similarity_explanation` is present, show those instead of `explanation`
- When `is_rated` is true, show a small "Seen" chip on the card

```typescript
// The card can detect which mode it's in:
const isSimilarMode = computed(() => 'similarity_score' in props.recommendation)
```

Alternatively, define a union prop:
```typescript
const props = defineProps<{
  recommendation: Recommendation | SimilarTitle
}>()
```

### 2. Add seen/unseen toggle to `FilterDrawer.vue`

Add a new expansion panel (or a simple toggle above the existing panels) for the seen/unseen filter. This should only be visible on the `/similar` page.

```html
<!-- Only show on similar page -->
<template v-if="route.path === '/similar'">
  <v-expansion-panel value="seen">
    <v-expansion-panel-title class="filter-section-title">Seen Status</v-expansion-panel-title>
    <v-expansion-panel-text>
      <v-btn-toggle v-model="similar.seenFilter" density="compact" color="primary" class="mb-2">
        <v-btn :value="null">All</v-btn>
        <v-btn :value="false">Unseen Only</v-btn>
        <v-btn :value="true">Seen Only</v-btn>
      </v-btn-toggle>
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>
```

When `seenFilter` changes, trigger a re-fetch of similar results with the `seen` query parameter.

### 3. Wire filters to the similar store

The filter sidebar already watches filter state and calls `recommendations.applyFilters()`. On the similar page, it should instead call `similar.applyFilters()`. Options:

- Use `useRoute()` to detect the current page and call the appropriate store
- Or emit a generic `@filters-changed` event that each page handles differently

The simplest approach: in the `watch` callback inside `FilterDrawer.vue`, check the current route and dispatch to the correct store.

### 4. Display results in `similar.vue`

The results grid in `similar.vue`:

```html
<div v-if="similar.similarResults" class="card-grid">
  <RecommendationCard
    v-for="item in similar.similarResults.results"
    :key="item.imdb_id ?? item.title"
    :recommendation="item"
    @dismissed="similar.handleDismissed"
    @exclude-genre="handleExcludeGenre"
    @exclude-language="handleExcludeLanguage"
  />
</div>
```

Show a summary above the grid: "Showing N titles similar to **Seed Title** (out of M candidates)"

### 5. Sort controls

Add a simple sort dropdown above the grid:
- **Most Similar** (default) — sort by `similarity_score` desc
- **Best Match** — sort by `predicted_score` desc (predicted taste score)
- **IMDB Rating** — sort by `imdb_rating` desc
- **Newest** — sort by `year` desc

Sorting is client-side on the already-fetched results.

## Acceptance Criteria

- [ ] Similar results display in the same card grid layout as recommendations
- [ ] Cards show similarity score as percentage (e.g., "87% match")
- [ ] Cards show similarity explanation instead of recommendation explanation
- [ ] Cards show a "Seen" badge when the title is in the user's rated list
- [ ] Seen/unseen toggle in the filter sidebar filters results correctly
- [ ] Changing filters re-fetches similar results with updated parameters
- [ ] Sort controls allow reordering by similarity, predicted score, IMDB rating, or year
- [ ] Dismissing a title from the similar results works (same as recommendations)
- [ ] `cd frontend && npx nuxt typecheck` passes
- [ ] `uv run pytest tests/ -q` passes
