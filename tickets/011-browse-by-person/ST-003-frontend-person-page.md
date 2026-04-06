---
ticket: "011"
subtask: 3
title: "Frontend: Person Browse Page with Search"
status: Done
effort: medium
component: frontend
depends_on: [1]
files_modified:
  - frontend/app/layouts/default.vue
  - frontend/app/composables/useApi.ts
  - frontend/app/types/index.ts
files_created:
  - frontend/app/pages/person.vue
  - frontend/app/stores/person.ts
---

# SUBTASK 03: Frontend — Person Browse Page with Search

---

## Objective

Add a `/person` page with a person-name autocomplete search bar and basic page scaffold.
Navigation link added to the app bar. No results grid yet — that is ST-004.

## Pre-conditions

- ST-001 is `Done`: `GET /api/v1/people/search` is live
- Read `frontend/app/pages/similar.vue` and `frontend/app/stores/similar.ts` in full before
  starting — this subtask is structurally identical to how `/similar` was built in ticket 009

```bash
cd frontend && npx nuxt typecheck
uv run pytest tests/ -q
```

## Context

The `/similar` page (ticket 009 ST-003) is the direct structural parallel: a search
autocomplete that calls a backend endpoint, stores the selected seed, and routes to a
results view. Reuse the same patterns and composable approach rather than inventing new
ones.

## Implementation

### 1. Add types to `types/index.ts`

```typescript
export interface PersonSearchResult {
  name_id: string
  name: string
  primary_profession: string | null
  title_count: number
}

export interface PersonTitleResult {
  imdb_id: string
  title: string
  year: number | null
  title_type: string
  imdb_rating: number | null
  num_votes: number | null
  runtime_minutes: number | null
  genres: string[]
  predicted_score: number
  explanation: string[]
  similar_to: string[]
  languages: string[]
  roles: string[]
}

export interface PersonTitlesResponse {
  name_id: string
  name: string
  primary_profession: string | null
  total: number
  results: PersonTitleResult[]
}
```

### 2. Add API methods to `useApi.ts`

```typescript
const searchPeople = async (q: string): Promise<PersonSearchResult[]> => {
  if (q.length < 2) return []
  const data = await $fetch<PersonSearchResult[]>(`${apiBase}/people/search`, {
    params: { q },
  })
  return data
}

const getTitlesByPerson = async (
  nameId: string,
  filters: Record<string, unknown> = {},
): Promise<PersonTitlesResponse> => {
  return $fetch<PersonTitlesResponse>(`${apiBase}/people/${nameId}`, {
    params: filters,
  })
}
```

Follow the exact same pattern used for the similar-page composable calls (read `useApi.ts`
for the existing `$fetch` and `apiBase` conventions before writing).

### 3. Create `stores/person.ts`

```typescript
export const usePersonStore = defineStore('person', () => {
  const selectedPerson = ref<PersonSearchResult | null>(null)
  const personResults = ref<PersonTitlesResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function searchPerson(nameId: string, filters = {}) {
    if (!selectedPerson.value) return
    loading.value = true
    error.value = null
    try {
      const api = useApi()
      personResults.value = await api.getTitlesByPerson(nameId, filters)
    } catch (e) {
      error.value = 'Failed to load titles. Has the pipeline been run?'
    } finally {
      loading.value = false
    }
  }

  function selectPerson(person: PersonSearchResult | null) {
    selectedPerson.value = person
    personResults.value = null
  }

  return { selectedPerson, personResults, loading, error, searchPerson, selectPerson }
})
```

### 4. Create `pages/person.vue`

Scaffold the page with:
- A `v-autocomplete` that calls `searchPeople` as the user types (debounced, min 2 chars)
- On selection, calls `person.selectPerson(item)` and then `person.searchPerson(item.name_id)`
- A loading spinner while `person.loading` is true
- An empty state message when no person is selected ("Search for a director or actor above")
- A placeholder area for the results grid (filled in ST-004)

```html
<template>
  <v-container>
    <v-row>
      <v-col cols="12" md="8" offset-md="2">
        <v-autocomplete
          v-model="selectedItem"
          v-model:search="searchQuery"
          :items="searchResults"
          :loading="searching"
          item-title="name"
          item-value="name_id"
          return-object
          label="Search for a director or actor"
          placeholder="e.g. Akira Kurosawa"
          no-filter
          clearable
          @update:search="onSearch"
          @update:model-value="onSelect"
        >
          <template #item="{ props, item }">
            <v-list-item v-bind="props">
              <template #subtitle>
                {{ item.raw.primary_profession }} · {{ item.raw.title_count }} titles
              </template>
            </v-list-item>
          </template>
        </v-autocomplete>
      </v-col>
    </v-row>

    <!-- Results grid slot — wired up in ST-004 -->
    <div v-if="person.loading" class="text-center py-8">
      <v-progress-circular indeterminate color="primary" />
    </div>
    <div v-else-if="!person.selectedPerson" class="text-center text-medium-emphasis py-12">
      Search for a director or actor above to see their top-ranked titles.
    </div>
    <!-- results slot here -->
  </v-container>
</template>
```

Follow the same `v-autocomplete` pattern used in `similar.vue` (debounce, `no-filter`,
`return-object`).

### 5. Add nav link to `layouts/default.vue`

Add a "By Person" nav item alongside the existing "Find Similar" link. Read the current
nav structure in `default.vue` before adding to match the exact component and style used.

## Acceptance Criteria

- [ ] Navigating to `/person` renders the page without console errors
- [ ] "By Person" link appears in the app bar
- [ ] Typing 2+ characters in the search bar fetches `GET /api/v1/people/search?q=...`
- [ ] Dropdown shows person name, profession, and title count
- [ ] Selecting a person triggers `GET /api/v1/people/{name_id}` and stores the result
- [ ] Loading spinner shows while the request is in flight
- [ ] Empty state message shows when no person is selected
- [ ] `cd frontend && npx nuxt typecheck` passes

## Commit Message

```
feat: add /person page with person search autocomplete and navigation
```
