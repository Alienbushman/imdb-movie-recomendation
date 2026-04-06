---
id: ST-001
ticket: "008"
title: "Client-Side Sort Controls"
priority: Medium
risk: low
status: Done
dependencies: []
subsystems: [frontend]
---

# ST-001 — Client-Side Sort Controls

**Priority:** Medium
**Risk:** Low
**Files:** `frontend/app/stores/recommendations.ts`, `frontend/app/pages/index.vue`, `frontend/app/types/index.ts`

## Problem

`currentList` in `recommendations.ts` is a plain `computed` that reads `data.value[tab.value]`
directly. The order is fixed by whatever the backend returned. Users can't reorder by IMDB
rating, year, vote count, or title.

## Pre-conditions

```bash
# Confirm currentList exists in the store
grep -n "currentList" frontend/app/stores/recommendations.ts
# Expected: at least 1 match

# Confirm persistence plugin is installed (from ticket 006 or install here)
grep -c "persistedstate" frontend/package.json
# Expected: 1 (if 0, install @pinia-plugin-persistedstate/nuxt first)
```

## Fix

Read all three files before editing to confirm the current state.

### Step 1 — `types/index.ts` — add `SortOption` type

```ts
export type SortOption = 'score' | 'imdb_rating' | 'year_desc' | 'year_asc' | 'votes' | 'title'
```

### Step 2 — `recommendations.ts` — add sort state and modify `currentList`

Add a per-tab sort ref:

```ts
const sortBy = ref<Record<ContentTab, SortOption>>({
  movies: 'score',
  series: 'score',
  anime: 'score',
})
```

Change `currentList` to apply sorting:

```ts
const currentList = computed(() => {
  if (!data.value) return []
  const list = [...(data.value[tab.value] || [])]
  const sort = sortBy.value[tab.value]
  switch (sort) {
    case 'imdb_rating':
      return list.sort((a, b) => (b.imdb_rating ?? -1) - (a.imdb_rating ?? -1))
    case 'year_desc':
      return list.sort((a, b) => (b.year ?? -1) - (a.year ?? -1))
    case 'year_asc':
      return list.sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999))
    case 'votes':
      return list.sort((a, b) => b.num_votes - a.num_votes)
    case 'title':
      return list.sort((a, b) => a.title.localeCompare(b.title))
    default: // 'score'
      return list.sort((a, b) => b.predicted_score - a.predicted_score)
  }
})
```

Expose `sortBy` from the store. Add `sortBy` to the persistence `pick` array.

### Step 3 — `index.vue` — add sort bar

Add a sort bar div between the filter summary chips and the `v-progress-linear`:

```html
<div class="d-flex align-center ga-2 mb-2">
  <span class="text-caption text-medium-emphasis">Showing {{ recommendations.currentList.length }}</span>
  <v-spacer />
  <v-select
    v-model="recommendations.sortBy[recommendations.tab]"
    :items="sortOptions"
    item-title="label"
    item-value="value"
    density="compact"
    hide-details
    variant="outlined"
    style="max-width: 180px"
    prepend-inner-icon="mdi-sort"
  />
</div>
```

Define sort options locally in `<script setup>`:

```ts
const sortOptions = [
  { label: 'Best Match', value: 'score' },
  { label: 'IMDB Rating', value: 'imdb_rating' },
  { label: 'Newest', value: 'year_desc' },
  { label: 'Oldest', value: 'year_asc' },
  { label: 'Most Voted', value: 'votes' },
  { label: 'A–Z', value: 'title' },
]
```

## Anti-patterns

- Do NOT mutate the original `data.value` array — always spread to a new array before sorting
- Do NOT add a sort API endpoint — sorting is purely client-side on the fetched list
- Do NOT persist `tab` — it should always default to Movies on page load

## Post-conditions

```bash
# Confirm SortOption type exists
grep -n "SortOption" frontend/app/types/index.ts
# Expected: 1 match

# Confirm sortBy is in the store
grep -n "sortBy" frontend/app/stores/recommendations.ts
# Expected: at least 2 matches

# Confirm sort select is in the template
grep -n "sortOptions" frontend/app/pages/index.vue
# Expected: at least 1 match
```

## Tests

```bash
# Frontend types
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/types/index.ts
frontend/app/stores/recommendations.ts
frontend/app/pages/index.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: add client-side sort controls with per-tab persistence
```
