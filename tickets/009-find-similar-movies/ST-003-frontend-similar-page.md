---
ticket: "009"
subtask: 3
title: "Frontend: Similar Page with Search + Routing"
status: done
effort: medium
component: frontend
depends_on: [1]
files_modified:
  - frontend/app/layouts/default.vue
  - frontend/app/composables/useApi.ts
  - frontend/app/types/index.ts
files_created:
  - frontend/app/pages/similar.vue
  - frontend/app/stores/similar.ts
---

# SUBTASK 03: Frontend — Similar Page with Search + Routing

---

## Objective

Create a new `/similar` page with a search bar (autocomplete typeahead) for finding a seed title, wire up the API composable, and add navigation in the app bar.

## Context

The app currently has two pages: `/` (recommendations) and `/dismissed`. This subtask adds a third page at `/similar`. The page needs a prominent search bar that queries `GET /api/v1/search` as the user types, letting them select a title to find similar content.

The layout should mirror the recommendations page: filter sidebar on the left, main content area on the right. The filter sidebar is currently defined inline in `index.vue` as the `<FilterDrawer />` component. It should be reusable on the similar page as well.

## Implementation

### 1. Add types to `types/index.ts`

```typescript
export interface TitleSearchResult {
  imdb_id: string
  title: string
  year: number | null
  title_type: string
  is_rated: boolean
}

export interface SimilarTitle {
  title: string
  title_type: string
  year: number | null
  genres: string[]
  imdb_rating: number | null
  predicted_score: number | null
  similarity_score: number
  similarity_explanation: string[]
  actors: string[]
  director: string | null
  language: string | null
  imdb_id: string | null
  imdb_url: string | null
  num_votes: number
  country_code: string | null
  is_rated: boolean
}

export interface SimilarResponse {
  seed_title: string
  seed_imdb_id: string
  results: SimilarTitle[]
  total_candidates: number
}
```

### 2. Add API methods to `useApi.ts`

```typescript
function searchTitles(query: string, limit = 20) {
  return fetchApi<TitleSearchResult[]>('/search', { query: { q: query, limit } })
}

function getSimilarTitles(
  imdbId: string,
  filters?: RecommendationFilters,
  topN = 50,
  seen?: boolean | null,
) {
  const query: Record<string, unknown> = { ...buildFilterQuery(filters), top_n: topN }
  if (seen != null) query.seen = seen
  return fetchApi<SimilarResponse>(`/similar/${imdbId}`, { query })
}
```

### 3. Create `stores/similar.ts`

A Pinia store managing the similar page state:

```typescript
export const useSimilarStore = defineStore('similar', () => {
  // Search state
  const searchQuery = ref('')
  const searchResults = ref<TitleSearchResult[]>([])
  const searchLoading = ref(false)

  // Selected seed
  const selectedSeed = ref<TitleSearchResult | null>(null)

  // Similar results
  const similarResults = ref<SimilarResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Seen filter: null = all, true = only seen, false = only unseen
  const seenFilter = ref<boolean | null>(null)

  // Search (debounced, called from autocomplete)
  async function search(query: string) { ... }

  // Fetch similar titles for selected seed
  async function fetchSimilar() { ... }

  // Apply filters (re-fetch with current filters)
  async function applyFilters() { ... }

  return { ... }
})
```

### 4. Add nav link in `default.vue`

Add a "Find Similar" button in the app bar's `#append` template, between the title and the "Dismissed" button:

```html
<v-btn to="/similar" variant="text" prepend-icon="mdi-movie-search">
  Find Similar
</v-btn>
```

### 5. Create `pages/similar.vue`

Page layout:
- Same `d-flex` structure as `index.vue`: `<FilterDrawer />` on left, main content on right
- Top of main content: `v-autocomplete` search bar
  - Uses `searchTitles` API for items
  - Shows title, year, type badge, and "rated" chip in item slots
  - On selection, triggers `fetchSimilar()`
- Below search: seed title summary card (shows what you selected)
- Below that: results grid using the same `card-grid` CSS class
- Empty state when no seed selected: prompt user to search for a title

The `v-autocomplete` configuration:
- `v-model` bound to `selectedSeed`
- `:items` bound to `searchResults`
- `item-title` = title display (e.g., "Inception (2010)")
- `item-value` = the full `TitleSearchResult` object
- `:loading` bound to `searchLoading`
- `@update:search` triggers debounced search (300ms)
- `no-filter` — server-side filtering, not client-side
- `return-object` — so we get the full object, not just the value

## Acceptance Criteria

- [ ] `/similar` page is accessible via the app bar navigation
- [ ] Search bar queries `GET /api/v1/search` as user types (debounced)
- [ ] Autocomplete dropdown shows title, year, type, and rated badge
- [ ] Selecting a title fetches and displays similar results
- [ ] Page uses FilterDrawer sidebar (same filters as recommendations)
- [ ] `cd frontend && npx nuxt typecheck` passes
