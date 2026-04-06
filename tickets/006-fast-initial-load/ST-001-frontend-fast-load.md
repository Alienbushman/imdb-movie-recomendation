---
id: ST-001
ticket: "006"
title: "Try Fast Path on Page Mount"
priority: High
risk: low
status: Done
dependencies: []
subsystems: [frontend]
---

# ST-001 — Try Fast Path on Page Mount

**Priority:** High
**Risk:** Low
**Files:** `frontend/package.json`, `frontend/nuxt.config.ts`, `frontend/app/stores/recommendations.ts`, `frontend/app/pages/index.vue`

## Problem

`onMounted` in `index.vue` calls `generate()`, which always hits `POST /recommendations`
(full pipeline). When `scored_candidates.db` already contains valid scores, the fast path
(`POST /recommendations/filter`) should be used instead. Additionally, `pipelineReady`
resets to `false` on every page reload because Pinia state is in-memory, so even
`applyFilters()` would fall back to `generate()`.

## Pre-conditions

```bash
# Confirm generate() is called on mount
grep -n "onMounted.*generate" frontend/app/pages/index.vue
# Expected: at least 1 match

# Confirm pipelineReady exists in the store
grep -n "pipelineReady" frontend/app/stores/recommendations.ts
# Expected: at least 1 match

# Confirm no persistence plugin is installed yet
grep -c "persistedstate" frontend/package.json
# Expected: 0
```

## Fix

Read all four files before editing to confirm the current state.

### Step 1 — Install persistence plugin

```bash
cd frontend && npm install @pinia-plugin-persistedstate/nuxt
```

### Step 2 — `nuxt.config.ts` — add module

Add `'@pinia-plugin-persistedstate/nuxt'` to the `modules` array, after `'@pinia/nuxt'`.

### Step 3 — `recommendations.ts` — add `loadOrGenerate()` and persistence

Add a `loadOrGenerate()` function to the store:

```ts
async function loadOrGenerate() {
  console.log('[recommendations] loadOrGenerate — trying fast path first')
  loading.value = true
  error.value = null
  let shouldGenerate = false
  try {
    data.value = await api.filterRecommendations(filtersStore.buildFilters())
    pipelineReady.value = true
    lastOperation.value = 'filter'
    console.log('[recommendations] loadOrGenerate — fast path OK')
  } catch (e: unknown) {
    const err = e as ApiError
    if (err.status === 409) {
      pipelineReady.value = false
      console.log('[recommendations] loadOrGenerate — no cached scores, running full pipeline')
      shouldGenerate = true
    } else {
      error.value = extractErrorMessage(e, 'Failed to load recommendations')
      console.error('[recommendations] loadOrGenerate — FAILED:', error.value)
    }
  } finally {
    loading.value = false
  }
  if (shouldGenerate) {
    return generate()
  }
}
```

Add persistence config to the store's `defineStore` options:

```ts
}, {
  persist: {
    pick: ['pipelineReady', 'lastOperation'],
  },
})
```

Expose `loadOrGenerate` in the store's return object.

### Step 4 — `index.vue` — call `loadOrGenerate` on mount

Replace the existing `onMounted(() => recommendations.generate())` with:

```ts
onMounted(() => recommendations.loadOrGenerate())
```

No other changes to `index.vue`.

## Anti-patterns

- Do NOT persist `data` or `tab` to localStorage — `data` is re-fetched on every mount,
  `tab` should always default to Movies
- Do NOT remove the existing `generate()` function — it is still used by the "Generate"
  and "Retrain" buttons
- Do NOT catch all errors and silently fall back to generate — only a 409 status means
  "no cached scores". Other errors should surface to the user.

## Post-conditions

```bash
# Confirm loadOrGenerate exists
grep -n "loadOrGenerate" frontend/app/stores/recommendations.ts
# Expected: at least 2 matches (definition + return)

# Confirm persistence config exists
grep -n "persist" frontend/app/stores/recommendations.ts
# Expected: at least 1 match

# Confirm mount calls loadOrGenerate
grep -n "loadOrGenerate" frontend/app/pages/index.vue
# Expected: at least 1 match

# Confirm old generate-on-mount is gone
grep -c "onMounted.*generate()" frontend/app/pages/index.vue
# Expected: 0
```

## Tests

```bash
# Frontend types
cd frontend && npx nuxt typecheck

# Backend tests (should be unaffected)
uv run pytest tests/ -q
```

## Files Changed

```
frontend/package.json
frontend/nuxt.config.ts
frontend/app/stores/recommendations.ts
frontend/app/pages/index.vue
```

## Rollback

```bash
git revert HEAD
cd frontend && npm install  # restore package.json/lock
```

## Commit Message

```
feat: try fast path on page mount with persisted pipeline state
```
