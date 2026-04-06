---
id: "008"
title: "Client-Side Sorting and UX Polish"
status: open
priority: medium
component: frontend
files_affected:
  - frontend/app/pages/index.vue
  - frontend/app/stores/recommendations.ts
  - frontend/app/components/RecommendationCard.vue
  - frontend/app/stores/filters.ts
  - frontend/app/types/index.ts
---

# TICKET-008: Client-Side Sorting and UX Polish

---

## Summary

The recommendations grid has no sorting controls — results come back from the backend ranked by predicted score and that's the only order available. Users may want to sort by IMDB rating, year, or vote count to cross-check recommendations. Additionally, a few small UX gaps are worth closing in the same pass: there's no "back to top" affordance on long lists, result counts are only visible via tab badges, and the grid is locked to two columns regardless of how many results are loaded.

All changes in this ticket are pure frontend (no backend or schema changes).

---

## Problem Details

### No sorting
`currentList` in `recommendations.ts` is a plain `computed` that reads `data.value[tab.value]` directly. The order is fixed by whatever the backend returned. Users can't reorder by:
- IMDB rating (useful to filter out highly-scored-but-low-rated titles)
- Year (newest or oldest first)
- Vote count (a proxy for cultural relevance)
- Title (alphabetical, handy for scanning a long list)

### No "back to top"
The card grid can be 20-30+ cards tall. Once a user scrolls down, they have to scroll all the way back up to reach the filter sidebar, tabs, or action buttons. There is no scroll-to-top affordance.

### Grid density is fixed
`card-grid` in `index.vue` is hardcoded to 2 columns below 1280px and 3 above. Users with wide monitors looking at 20+ results may prefer 4 columns; users who want to read explanations carefully may prefer 2.

### Result count is only visible on tab badges
The tab badges show counts, but disappear once you're on a tab. There's no persistent "Showing 20 results" label above the grid that lets users know at a glance how many recommendations matched their current filters.

---

## Solution

### Subtask 1 — Sort controls

Add a sort state to the recommendations store. `currentList` becomes a sorted computed that applies the selected sort on top of the raw tab data.

**Sort options:**

| Label | Sort key | Direction |
|---|---|---|
| Best Match | `predicted_score` | desc |
| IMDB Rating | `imdb_rating` | desc (nulls last) |
| Newest | `year` | desc (nulls last) |
| Oldest | `year` | asc (nulls first) |
| Most Voted | `num_votes` | desc |
| A–Z | `title` | asc |

Render a `v-btn-toggle` or `v-select` in a new "sort bar" `div` placed between the active filter summary chips and the `v-progress-linear` loading indicator in `index.vue`. Keep it compact — `density="compact"` and left-aligned so it doesn't compete with the action buttons.

Sort state should be **per-tab** (object keyed by `ContentTab`), so switching from Movies to Series doesn't reset your sort. Default is `predicted_score` desc for all tabs. Persist to `localStorage` via `@pinia-plugin-persistedstate/nuxt` alongside the existing persistence from ticket 006.

### Subtask 2 — Scroll-to-top FAB

Add a `v-fab` (or a `v-btn` with `position="fixed"`) in the bottom-right corner of the main content area. It should:
- Only appear when the user has scrolled the content area more than ~300px
- Scroll the content area (`div.flex-grow-1.overflow-auto`) back to top when clicked
- Use icon `mdi-chevron-double-up`, small size, `color="primary"`, `variant="tonal"`

Track scroll state via a `scroll` event listener on the content div in `onMounted` / `onUnmounted`.

### Subtask 3 — Grid density toggle + result count

**Density toggle**: Add two icon buttons in the sort bar (right-aligned): `mdi-view-grid` (3-col dense) and `mdi-view-grid-outline` (2-col comfortable). Toggle a `gridDense` ref in the page. When dense, `card-grid` uses `repeat(auto-fill, minmax(280px, 1fr))`; when comfortable, `repeat(auto-fill, minmax(360px, 1fr))`. Persist preference in `localStorage` (a simple `useLocalStorage` composable from `@vueuse/core` is sufficient — no Pinia store needed).

**Result count**: In the sort bar, show `<span class="text-caption text-medium-emphasis">Showing {{ currentList.length }}</span>` on the left side, before the sort controls.

---

## Subtasks

| # | File | Title |
|---|------|-------|
| 1 | [ST-001-sort-controls.md](008-sorting-and-ux-polish/ST-001-sort-controls.md) | Client-side sort controls |
| 2 | [ST-002-scroll-to-top.md](008-sorting-and-ux-polish/ST-002-scroll-to-top.md) | Scroll-to-top FAB |
| 3 | [ST-003-density-and-count.md](008-sorting-and-ux-polish/ST-003-density-and-count.md) | Grid density toggle + result count label |

All subtasks are independent and can run in parallel.

---

## Acceptance Criteria

- [ ] A sort control is visible above the card grid on every tab
- [ ] Sort options: Best Match, IMDB Rating, Newest, Oldest, Most Voted, A–Z
- [ ] Changing tabs does not reset the sort order on the previous tab
- [ ] Sort state survives a page reload (persisted via `localStorage`)
- [ ] A "back to top" button appears after scrolling down ~300px and scrolls the content area to top
- [ ] The sort bar shows "Showing N" reflecting the current filtered list length
- [ ] Grid density can be toggled between comfortable (wide cards) and dense (narrow cards)
- [ ] Grid density preference survives a page reload
- [ ] Lint passes: `cd frontend && npx nuxt typecheck`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`

---

## Non-Goals

- No backend changes — sorting is applied client-side on the already-fetched list
- No new API fields — `Recommendation` schema is unchanged
- No server-side pagination — out of scope
