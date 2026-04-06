---
id: ST-003
ticket: "010"
title: "Extract CategoryTabs Component"
priority: Medium
risk: low
status: Open
dependencies: [ST-002]
subsystems: [frontend]
---

# ST-003 — Extract CategoryTabs Component

**Priority:** Medium
**Risk:** Low
**Files modified:** `frontend/app/pages/index.vue`
**Files created:** `frontend/app/components/CategoryTabs.vue`

## Problem

The category tabs block (lines ~176–204 in `index.vue`) renders Movies/Series/Anime
tabs with badge counts. It's a small, stable UI block that adds template noise to the
page.

## Fix

Read `frontend/app/pages/index.vue` before editing.

### Step 1 — Create `CategoryTabs.vue`

Props and v-model:

```typescript
const tab = defineModel<string>({ required: true })

defineProps<{
  movieCount: number
  seriesCount: number
  animeCount: number
}>()
```

Uses `v-model` for the active tab so the parent controls tab state (it lives in the
recommendations store).

### Step 2 — Update `index.vue`

Replace the tabs block with:

```html
<CategoryTabs
  v-model="recommendations.tab"
  :movie-count="recommendations.data?.movies.length ?? 0"
  :series-count="recommendations.data?.series.length ?? 0"
  :anime-count="recommendations.data?.anime.length ?? 0"
/>
```

## Anti-patterns

- Do NOT move tab state into the component — it must stay in the recommendations store
  because other parts of the app depend on it
- Preserve `data-e2e` attributes

## Post-conditions

```bash
test -f frontend/app/components/CategoryTabs.vue && echo "OK" || echo "MISSING"
grep -n "CategoryTabs" frontend/app/pages/index.vue
# Expected: at least 1 match
grep -c "v-tab" frontend/app/pages/index.vue
# Expected: 0 (tabs are now in the component)
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/pages/index.vue
frontend/app/components/CategoryTabs.vue (new)
```

## Commit Message

```
refactor: extract CategoryTabs component from index.vue
```
