---
id: ST-004
ticket: "010"
title: "Extract RecommendationGrid Component"
priority: Medium
risk: low
status: Open
dependencies: [ST-003]
subsystems: [frontend]
---

# ST-004 — Extract RecommendationGrid Component

**Priority:** Medium
**Risk:** Low-Medium
**Files modified:** `frontend/app/pages/index.vue`
**Files created:** `frontend/app/components/RecommendationGrid.vue`

## Problem

The recommendation grid area (lines ~207–260 in `index.vue`) contains three conditional
blocks (empty state, loading skeletons, card grid) plus the card-grid CSS. This is the
section that T008 subtasks (sort controls, scroll-to-top, grid density) all need to
modify. Extracting it means all three T008 subtasks target `RecommendationGrid.vue`
instead of `index.vue`, eliminating conflicts with T006.

## Fix

Read `frontend/app/pages/index.vue` before editing.

### Step 1 — Create `RecommendationGrid.vue`

Props:

```typescript
import type { Recommendation } from '../types'

defineProps<{
  items: Recommendation[]
  loading: boolean
  hasData: boolean
}>()

const emit = defineEmits<{
  generate: []
  dismissed: [imdbId: string]
  excludeGenre: [genre: string]
  excludeLanguage: [language: string]
}>()
```

Template includes:
- Empty state (`v-if="!hasData && !loading"`) with "Get Started" button emitting `generate`
- Loading skeletons (`v-else-if="loading && !hasData"`)
- Card grid (`v-else`) with `RecommendationCard` v-for
- The "no results" `v-alert` inside the grid
- The `v-progress-linear` loading indicator above the grid

Move the `<style scoped>` `.card-grid` CSS into this component.

### Step 2 — Update `index.vue`

Replace all three conditional blocks and the progress bar with:

```html
<RecommendationGrid
  :items="recommendations.currentList"
  :loading="recommendations.loading"
  :has-data="!!recommendations.data"
  @generate="recommendations.generate(false)"
  @dismissed="recommendations.handleDismissed"
  @exclude-genre="handleExcludeGenre"
  @exclude-language="handleExcludeLanguage"
/>
```

Remove the `.card-grid` CSS from `index.vue`.

### Step 3 — Verify index.vue is now slim

After all four extractions (ST-001 through ST-004), `index.vue` should be roughly:
- `<script setup>`: store imports, exclude handlers, `onMounted`, `handleCsvUpload` (~20 lines)
- `<template>`: FilterDrawer + 5 component tags + error alert (~30 lines)
- No `<style>` section

## Anti-patterns

- Do NOT move the recommendations store interaction into the grid component — it
  receives data via props and communicates via emits
- Do NOT remove the "Get Started" button's `generate` call — keep it as an emit
- Preserve all `data-e2e` attributes

## Post-conditions

```bash
test -f frontend/app/components/RecommendationGrid.vue && echo "OK" || echo "MISSING"
grep -n "RecommendationGrid" frontend/app/pages/index.vue
# Expected: at least 1 match
grep -c "card-grid" frontend/app/pages/index.vue
# Expected: 0 (CSS moved to component)
wc -l frontend/app/pages/index.vue
# Expected: under 80 lines
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/pages/index.vue
frontend/app/components/RecommendationGrid.vue (new)
```

## Commit Message

```
refactor: extract RecommendationGrid component from index.vue
```
