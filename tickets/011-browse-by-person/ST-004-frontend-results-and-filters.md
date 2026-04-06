---
ticket: "011"
subtask: 4
title: "Frontend: Results Display + Role Filter"
status: open
effort: medium
component: frontend
depends_on: [2, 3]
files_modified:
  - frontend/app/pages/person.vue
  - frontend/app/stores/person.ts
  - frontend/app/components/FilterDrawer.vue
  - frontend/app/components/RecommendationCard.vue
files_created: []
---

# SUBTASK 04: Frontend — Results Display + Role Filter

---

## Objective

Wire the person titles response into the card grid, add a role toggle (Director / Actor /
Any) above the results, connect the existing FilterDrawer to the person store, and show
the person's role on each result card.

## Pre-conditions

- ST-002 is `Done`: `GET /api/v1/people/{name_id}` returns `PersonTitlesResponse`
- ST-003 is `Done`: `/person` page scaffold exists with `usePersonStore`
- Read `frontend/app/pages/similar.vue` (ticket 009 ST-004 equivalent) and
  `frontend/app/components/RecommendationCard.vue` in full before writing

```bash
cd frontend && npx nuxt typecheck
uv run pytest tests/ -q
```

## Context

`PersonTitleResult` shares most fields with `Recommendation` but adds a `roles` list.
`RecommendationCard` currently handles `Recommendation` objects — after ticket 009 ST-004 it
may already accept a union prop. Read the current card implementation and determine whether
to extend the existing union or create a separate display path.

## Implementation

### 1. Display results grid in `person.vue`

Replace the results placeholder from ST-003 with the card grid:

```html
<template v-if="person.personResults">
  <v-row class="mb-4" align="center">
    <v-col>
      <span class="text-body-2 text-medium-emphasis">
        Showing {{ filteredResults.length }} of {{ person.personResults.total }} titles
        by <strong>{{ person.selectedPerson?.name }}</strong>
      </span>
    </v-col>
    <v-col cols="auto">
      <!-- Role toggle (see step 2) -->
    </v-col>
    <v-col cols="auto">
      <!-- Sort dropdown (see step 3) -->
    </v-col>
  </v-row>

  <div class="card-grid">
    <RecommendationCard
      v-for="item in filteredResults"
      :key="item.imdb_id"
      :recommendation="item"
      @dismissed="person.handleDismissed"
      @exclude-genre="handleExcludeGenre"
      @exclude-language="handleExcludeLanguage"
    />
  </div>
</template>
```

### 2. Add role toggle above the grid

```html
<v-btn-toggle
  v-model="roleFilter"
  density="compact"
  color="primary"
  mandatory
>
  <v-btn value="any">Any role</v-btn>
  <v-btn value="director">Director</v-btn>
  <v-btn value="actor">Actor</v-btn>
  <v-btn value="writer">Writer</v-btn>
</v-btn-toggle>
```

`roleFilter` is local ref. `filteredResults` is a computed:

```typescript
const filteredResults = computed(() => {
  const results = person.personResults?.results ?? []
  if (roleFilter.value === 'any') return results
  return results.filter(r => r.roles.includes(roleFilter.value))
})
```

Role filtering is client-side on the already-fetched results — no re-fetch needed.

### 3. Add sort dropdown

```html
<v-select
  v-model="sortBy"
  :items="sortOptions"
  density="compact"
  style="max-width: 180px"
/>
```

```typescript
const sortOptions = [
  { title: 'Best Match',   value: 'predicted_score' },
  { title: 'IMDB Rating',  value: 'imdb_rating' },
  { title: 'Newest',       value: 'year' },
  { title: 'Most Votes',   value: 'num_votes' },
]
const sortBy = ref('predicted_score')

const filteredResults = computed(() => {
  let results = person.personResults?.results ?? []
  if (roleFilter.value !== 'any')
    results = results.filter(r => r.roles.includes(roleFilter.value))
  return [...results].sort(
    (a, b) => ((b[sortBy.value] ?? 0) as number) - ((a[sortBy.value] ?? 0) as number),
  )
})
```

### 4. Show role badge on `RecommendationCard.vue`

`PersonTitleResult` includes a `roles` field. When present, show the roles as small chips
below the title. Detect person-mode with:

```typescript
const isPersonMode = computed(() => 'roles' in props.recommendation)
```

Render:

```html
<template v-if="isPersonMode && recommendation.roles?.length">
  <div class="mt-1">
    <v-chip
      v-for="role in recommendation.roles"
      :key="role"
      size="x-small"
      variant="tonal"
      class="mr-1 text-capitalize"
    >{{ role }}</v-chip>
  </div>
</template>
```

Keep the change minimal — only add the role chip block; do not restructure the card.

### 5. Wire FilterDrawer to person store

Read how `similar.vue` wires the FilterDrawer before replicating the pattern.
When `FilterDrawer` emits a filters-changed event on the `/person` page, call
`person.searchPerson(person.selectedPerson.name_id, updatedFilters)` to re-fetch with
new scalar filter values from the sidebar.

Add `handleDismissed` to `usePersonStore`:

```typescript
function handleDismissed(imdbId: string) {
  if (!personResults.value) return
  personResults.value.results = personResults.value.results.filter(
    r => r.imdb_id !== imdbId,
  )
}
```

## Acceptance Criteria

- [ ] Selecting a person shows their titles in the same card grid layout as recommendations
- [ ] The role toggle filters the displayed results client-side with no additional requests
- [ ] Sort controls reorder results by predicted score, IMDB rating, year, or vote count
- [ ] Each card shows the person's role(s) as small chips when in person-browse mode
- [ ] The filter sidebar re-fetches with updated scalar parameters when filters change
- [ ] Dismissing a title removes it from the person results immediately
- [ ] `cd frontend && npx nuxt typecheck` passes
- [ ] `uv run pytest tests/ -q` passes

## Commit Message

```
feat: add results grid, role filter, and sort controls to person browse page
```
