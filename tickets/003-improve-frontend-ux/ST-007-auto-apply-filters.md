---
ticket: "003"
subtask: 7
title: "Auto-Apply Filters with Debounce"
status: done
effort: low
component: frontend
depends_on: [1]
files_modified:
  - frontend/app/pages/index.vue
  - frontend/app/stores/filters.ts
  - frontend/app/stores/recommendations.ts
files_created: []
---

# SUBTASK 07: Auto-Apply Filters with Debounce

---

## Objective

Automatically apply filters when the user changes any filter value, with debouncing to avoid excessive API calls. Remove the manual "Apply Filters" button in favor of instant, reactive filtering.

## Context

Currently, the user must:
1. Open the filter drawer
2. Change one or more filter values
3. Click "Apply Filters" button
4. Wait for results

This creates unnecessary friction, especially for exploratory filtering where users want to quickly try different combinations. Modern filter UIs (Netflix, Spotify, e-commerce sites) apply changes immediately as you interact.

The backend's `POST /recommendations/filter` endpoint is fast (milliseconds — it reuses cached scores), so debounced auto-apply won't cause performance issues.

### Current flow
- `index.vue:344`: "Apply Filters" button calls `recommendations.applyFilters(); filterDrawer = false`
- `recommendations.ts:applyFilters()`: calls `api.filterRecommendations(filtersStore.buildFilters())`
- Filter drawer closes on apply

### Exclude-on-card already auto-applies
Genre and language exclusion via card chips already auto-apply (`index.vue:10-28`) — the pattern is established, it just needs to extend to all filters.

## Implementation

### 1. Add a debounced watcher on filter state

In the recommendations store (or in `index.vue`), watch all filter values and auto-apply:

```typescript
import { watchDebounced } from '@vueuse/core'
// or implement a simple debounce:

function useDebouncedFilter() {
  let timeout: ReturnType<typeof setTimeout> | null = null

  function scheduleApply() {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => {
      recommendations.applyFilters()
    }, 400) // 400ms debounce
  }

  return { scheduleApply }
}
```

### 2. Watch filter store changes

Watch all reactive filter values:

```typescript
watch(
  () => [
    filters.minYear,
    filters.maxYear,
    filters.selectedGenres,
    filters.excludedGenres,
    filters.selectedLanguage,
    filters.selectedCountryCode,
    filters.excludedLanguages,
    filters.minImdbRating,
    filters.maxRuntime,
    filters.minPredictedScore,
  ],
  () => {
    if (recommendations.pipelineReady) {
      scheduleApply()
    }
  },
  { deep: true }
)
```

The `pipelineReady` guard ensures auto-apply only fires after the initial generation. Before that, changing filters just queues them for the first full pipeline run.

### 3. Debounce strategy

- **Chip toggles (genres, languages):** Apply after 300ms — fast for discrete selections
- **Sliders (year range, IMDB rating, runtime, predicted score):** Apply after 500ms — slower to allow slider dragging without firing on every pixel
- **Text inputs / autocomplete:** Apply after 400ms — standard typing debounce

If different debounce times are too complex, use a single 400ms debounce for everything — it's a good middle ground.

### 4. Loading indicator during auto-apply

Since filters apply automatically, the user needs feedback that something is happening:

- Show a subtle progress bar or spinner on the recommendations grid during filtering
- Keep existing cards visible while loading (don't clear them)
- Optionally add a "Filtering..." text indicator near the filter summary chips

### 5. Remove manual "Apply" button

- Remove the "Apply Filters" button from the filter panel
- Keep the "Reset" button to clear all filters at once
- The filter panel no longer needs to close on apply — it stays open for continued exploration

### 6. Add VueUse dependency (if not already present)

If using `@vueuse/core` for `watchDebounced`:
```bash
cd frontend && npm install @vueuse/core
```

Alternatively, implement a simple debounce utility to avoid a new dependency:
```typescript
function debounce<T extends (...args: unknown[]) => void>(fn: T, ms: number) {
  let timeout: ReturnType<typeof setTimeout>
  return (...args: Parameters<T>) => {
    clearTimeout(timeout)
    timeout = setTimeout(() => fn(...args), ms)
  }
}
```

## Acceptance Criteria

- [x] Changing any filter value automatically triggers a debounced re-filter
- [x] Debounce delay is 300-500ms (not instant, not slow)
- [x] Auto-apply only fires after initial pipeline generation (`pipelineReady`)
- [x] Existing cards remain visible during re-filtering (no flash to empty state)
- [x] Subtle loading indicator shows during re-filter
- [x] "Apply Filters" button is removed; "Reset" button remains
- [x] Rapid filter changes (e.g., quickly toggling genres) don't cause race conditions or duplicate requests
- [x] No new external dependencies unless strictly necessary (prefer simple debounce utility)

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
