---
id: ST-002
ticket: "010"
title: "Extract ActiveFilterSummary Component"
priority: Medium
risk: low
status: Open
dependencies: [ST-001]
subsystems: [frontend]
---

# ST-002 — Extract ActiveFilterSummary Component

**Priority:** Medium
**Risk:** Low
**Files modified:** `frontend/app/pages/index.vue`
**Files created:** `frontend/app/components/ActiveFilterSummary.vue`

## Problem

The active filter summary bar (lines ~123–159 in `index.vue`) shows current filter
chips and exclusion chips with close buttons. It's a self-contained display concern
with its own conditional visibility logic.

## Fix

Read `frontend/app/pages/index.vue` before editing.

### Step 1 — Create `ActiveFilterSummary.vue`

Extract the filter summary `div` with all its chips. The component reads directly from
the filters store (it's a display-only component that reflects store state):

```typescript
import { useFiltersStore } from '../stores/filters'

const filters = useFiltersStore()

const emit = defineEmits<{
  removeExcludedGenre: [genre: string]
  removeExcludedLanguage: [language: string]
}>()
```

The component renders the entire `v-if="filters.activeFilterSummary.length || ..."` div.
Genre/language close buttons emit events upward rather than calling store methods
directly (the parent orchestrates the store + recommendation refresh).

### Step 2 — Update `index.vue`

Replace the extracted block with:

```html
<ActiveFilterSummary
  @remove-excluded-genre="removeExcludedGenreAndApply"
  @remove-excluded-language="removeExcludedLanguageAndApply"
/>
```

## Anti-patterns

- Do NOT duplicate filter state — the component reads from the filters store
- Preserve all chip `data-e2e` and `key` attributes

## Post-conditions

```bash
test -f frontend/app/components/ActiveFilterSummary.vue && echo "OK" || echo "MISSING"
grep -n "ActiveFilterSummary" frontend/app/pages/index.vue
# Expected: at least 1 match
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/pages/index.vue
frontend/app/components/ActiveFilterSummary.vue (new)
```

## Commit Message

```
refactor: extract ActiveFilterSummary component from index.vue
```
