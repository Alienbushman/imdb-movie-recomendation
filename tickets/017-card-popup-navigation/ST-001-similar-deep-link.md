---
id: ST-001
ticket: "017"
title: "Similar page deep-link support"
priority: Medium
risk: low
status: Done
dependencies: []
subsystems: [frontend]
---

# ST-001 — Similar Page Deep-Link Support

**Priority:** Medium
**Risk:** Low
**Files:** `frontend/app/stores/similar.ts`, `frontend/app/pages/similar.vue`

## Problem

The `/similar` page today only populates its seed via the autocomplete — there
is no way to arrive on the page already loaded for a given title. ST-003 will
introduce a **Find Similar** button on card popups that routes to
`/similar?imdb_id=...&title=...&year=...&title_type=...`, and the page must be
able to bootstrap from those query params.

Concretely:

- `useSimilarStore()` has no helper that accepts a pre-built `TitleSearchResult`
  and triggers `fetchSimilar()` in one call.
- `similar.vue` does not read `useRoute().query` on mount.

## Pre-conditions

```bash
# Confirm the store currently exposes fetchSimilar() keyed on selectedSeed
grep -n "fetchSimilar" frontend/app/stores/similar.ts
# Expected: at least one definition
```

```bash
# Confirm the page has no onMounted query-param handler yet
grep -n "useRoute" frontend/app/pages/similar.vue
# Expected: 0 matches
```

## Fix

### Step 1 — Add `selectSeedById` helper to the similar store

In [similar.ts](../../frontend/app/stores/similar.ts), add a new function
alongside `fetchSimilar` that takes a `TitleSearchResult`, assigns it as the
`selectedSeed`, and awaits `fetchSimilar()`:

```ts
async function selectSeedById(seed: TitleSearchResult) {
  selectedSeed.value = seed
  await fetchSimilar()
}
```

Export it from the store's return object so the page can call it.

### Step 2 — Read query params on mount in `similar.vue`

In [similar.vue](../../frontend/app/pages/similar.vue), import `useRoute` from
`#imports` (auto-imported in Nuxt 4) and add an `onMounted` block that reads
`imdb_id`, `title`, `year`, and `title_type` from the route query. If
`imdb_id` and `title` are present **and** there is no current `selectedSeed`,
construct a minimal seed and call the new store helper:

```ts
onMounted(() => {
  const route = useRoute()
  const q = route.query
  if (!similar.selectedSeed && typeof q.imdb_id === 'string' && typeof q.title === 'string') {
    similar.selectSeedById({
      imdb_id: q.imdb_id,
      title: q.title,
      year: q.year ? Number(q.year) : null,
      title_type: typeof q.title_type === 'string' ? q.title_type : 'movie',
      is_rated: false,
    })
  }
})
```

Guarding on `!similar.selectedSeed` prevents overwriting an existing selection
when the user navigates back to `/similar` in the same session.

## Anti-patterns

- Do NOT add a route watcher that refetches on every query change — only the
  initial mount should consume query params.
- Do NOT call `fetchSimilar()` directly from the page's `onMounted`; route all
  seed changes through the store so the `selectedSeed` ref stays authoritative.
- Do NOT add new fields to `TitleSearchResult`. The existing shape already
  contains every field the autocomplete's selection template reads.

## Post-conditions

```bash
# Confirm the new helper is exported
grep -n "selectSeedById" frontend/app/stores/similar.ts
# Expected: at least 2 matches (definition + return statement)
```

```bash
# Confirm the page reads route query on mount
grep -n "useRoute" frontend/app/pages/similar.vue
# Expected: at least 1 match
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

Manual smoke test (after ST-003 lands — not required for this subtask alone):
navigate to `/similar?imdb_id=tt1375666&title=Inception&year=2010&title_type=movie`
and verify the seed is populated and results load.

## Files Changed

```
frontend/app/stores/similar.ts
frontend/app/pages/similar.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: similar page deep-link support via query params (ST-001)
```
