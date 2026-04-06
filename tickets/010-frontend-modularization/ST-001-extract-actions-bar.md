---
id: ST-001
ticket: "010"
title: "Extract ActionsBar Component"
priority: Medium
risk: low
status: Open
dependencies: []
subsystems: [frontend]
---

# ST-001 — Extract ActionsBar Component

**Priority:** Medium
**Risk:** Low
**Files modified:** `frontend/app/pages/index.vue`
**Files created:** `frontend/app/components/ActionsBar.vue`

## Problem

The actions bar (Generate/Retrain buttons, Data Source toggle, operation/accuracy chips)
and the collapsible data source panel (IMDB URL + CSV upload) are defined inline in
`index.vue` (lines ~55–120). They are a self-contained concern that no other page uses
and that clutters the main page file.

## Fix

Read `frontend/app/pages/index.vue` before editing.

### Step 1 — Create `ActionsBar.vue`

Extract the following from `index.vue` into a new component:

- The `imdbUrl` ref and `showDataSource` ref
- The `handleCsvUpload` function
- The actions bar `div` (lines ~55–89): Generate, Retrain, Data Source toggle, spacer,
  last-operation chip, model-accuracy chip
- The collapsible data source `v-expand-transition` block (lines ~92–120): IMDB URL
  text field + CSV file input

Props:
```typescript
defineProps<{
  loading: boolean
  lastOperation: 'filter' | 'generate' | null
  modelAccuracy: number | null
}>()
```

Emits:
```typescript
defineEmits<{
  generate: [retrain: boolean, imdbUrl?: string]
  csvUploaded: [file: File]
}>()
```

The component uses its own local `imdbUrl` and `showDataSource` refs (they don't need
to be in the parent). The Generate button emits `generate(false, imdbUrl)`, the Retrain
button emits `generate(true, imdbUrl)`, and the CSV handler emits `csvUploaded(file)`.

### Step 2 — Update `index.vue`

Replace the extracted template blocks with:

```html
<ActionsBar
  :loading="recommendations.loading"
  :last-operation="recommendations.lastOperation"
  :model-accuracy="recommendations.data?.model_accuracy ?? null"
  @generate="(retrain, url) => recommendations.generate(retrain, url)"
  @csv-uploaded="handleCsvUpload"
/>
```

Move the `handleCsvUpload` function body into the parent's event handler (it calls
`api.uploadWatchlist` then `recommendations.generate()`).

Remove `imdbUrl` and `showDataSource` from `index.vue` — they now live in `ActionsBar`.

## Anti-patterns

- Do NOT pass the entire recommendations store as a prop — pass only the data the
  component needs
- Do NOT move API calls into ActionsBar — keep API interaction in the page or store
- Preserve all `data-e2e` attributes on the same elements

## Post-conditions

```bash
# Confirm ActionsBar exists
test -f frontend/app/components/ActionsBar.vue && echo "OK" || echo "MISSING"

# Confirm it's used in index.vue
grep -n "ActionsBar" frontend/app/pages/index.vue
# Expected: at least 1 match

# Confirm imdbUrl is NOT in index.vue
grep -c "imdbUrl" frontend/app/pages/index.vue
# Expected: 0

# Confirm data-e2e attributes preserved
grep -c "data-e2e" frontend/app/components/ActionsBar.vue
# Expected: at least 4
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/pages/index.vue
frontend/app/components/ActionsBar.vue (new)
```

## Commit Message

```
refactor: extract ActionsBar component from index.vue
```
