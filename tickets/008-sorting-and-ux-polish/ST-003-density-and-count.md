---
id: ST-003
ticket: "008"
title: "Grid Density Toggle + Result Count Label"
priority: Low
risk: zero
status: Done
dependencies: []
subsystems: [frontend]
---

# ST-003 — Grid Density Toggle + Result Count Label

**Priority:** Low
**Risk:** Zero
**Files:** `frontend/app/pages/index.vue`

## Problem

The grid is locked to a fixed column layout regardless of screen size or user preference.
Users with wide monitors may prefer more columns; users reading explanations may prefer fewer.
Additionally, result counts are only visible on tab badges and disappear once on a tab.

## Pre-conditions

```bash
# Confirm card-grid class exists
grep -n "card-grid" frontend/app/pages/index.vue
# Expected: at least 1 match

# Check if @vueuse/core is available
grep -c "vueuse" frontend/package.json
# Expected: note result — if 0, use plain localStorage pattern instead
```

## Fix

Read `frontend/app/pages/index.vue` before editing to confirm the current state.

### Step 1 — Add density toggle state

If `@vueuse/core` is installed:
```ts
import { useLocalStorage } from '@vueuse/core'
const gridDense = useLocalStorage('grid-dense', false)
```

If not installed, use a plain pattern:
```ts
const gridDense = ref(localStorage.getItem('grid-dense') === 'true')
watch(gridDense, (v) => localStorage.setItem('grid-dense', String(v)))
```

### Step 2 — Update sort bar with density buttons

Update the sort bar div (from ST-001, or create if ST-001 not done yet):

```html
<div class="d-flex align-center ga-2 mb-2">
  <span class="text-caption text-medium-emphasis">
    Showing {{ recommendations.currentList.length }}
  </span>
  <v-spacer />
  <!-- sort select from ST-001 goes here if present -->
  <v-btn-toggle v-model="gridDense" density="compact" variant="outlined" mandatory>
    <v-btn :value="false" icon="mdi-view-grid-outline" size="small" />
    <v-btn :value="true" icon="mdi-view-grid" size="small" />
  </v-btn-toggle>
</div>
```

### Step 3 — Update card grid CSS

Replace the hardcoded card-grid columns with a density-aware class:

```html
<div
  data-e2e="recommendations-grid"
  class="card-grid"
  :class="{ 'card-grid--dense': gridDense }"
>
```

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.card-grid--dense {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
```

## Anti-patterns

- Do NOT add `@vueuse/core` as a dependency just for this — use the plain localStorage
  pattern if it's not already installed
- Do NOT persist density in the Pinia store — a simple localStorage value is sufficient
  for a single boolean preference

## Post-conditions

```bash
# Confirm density toggle exists
grep -n "gridDense" frontend/app/pages/index.vue
# Expected: at least 2 matches

# Confirm card-grid--dense class exists
grep -n "card-grid--dense" frontend/app/pages/index.vue
# Expected: at least 2 matches (class binding + CSS)

# Confirm "Showing" label exists
grep -n "Showing" frontend/app/pages/index.vue
# Expected: at least 1 match
```

## Tests

```bash
# Frontend types
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/pages/index.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: add grid density toggle and result count label
```
