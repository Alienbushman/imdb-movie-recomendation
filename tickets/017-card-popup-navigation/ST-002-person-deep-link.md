---
id: ST-002
ticket: "017"
title: "Person page deep-link support"
priority: Medium
risk: low
status: Done
dependencies: []
subsystems: [frontend]
---

# ST-002 — Person Page Deep-Link Support

**Priority:** Medium
**Risk:** Low
**Files:** `frontend/app/stores/person.ts`, `frontend/app/pages/person.vue`

## Problem

The `/person` page today only populates its selection via the autocomplete.
ST-004 will add clickable director/actor chips on card popups that route to
`/person?name_id=...&name=...`, and the page must bootstrap from those params.

Today:

- `usePersonStore()` has no helper that accepts a pre-built `PersonSearchResult`
  and triggers `fetchTitles()`.
- `person.vue` does not read `useRoute().query` on mount.

## Pre-conditions

```bash
grep -n "fetchTitles" frontend/app/stores/person.ts
# Expected: definition + return entry
```

```bash
grep -n "useRoute" frontend/app/pages/person.vue
# Expected: 0 matches
```

## Fix

### Step 1 — Add `selectPersonById` helper to the person store

In [person.ts](../../frontend/app/stores/person.ts), add a helper that takes a
`PersonSearchResult`, routes it through the existing `selectPerson` mutation,
and then awaits `fetchTitles()`:

```ts
async function selectPersonById(selection: PersonSearchResult) {
  selectPerson(selection)
  await fetchTitles()
}
```

Export it from the store's return object.

### Step 2 — Read query params on mount in `person.vue`

In [person.vue](../../frontend/app/pages/person.vue), add an `onMounted` block
that reads `name_id` and `name` from the route query. If both are present and
`selectedPerson` is null, build a minimal `PersonSearchResult` and call the
helper:

```ts
onMounted(() => {
  const route = useRoute()
  const q = route.query
  if (!person.selectedPerson && typeof q.name_id === 'string' && typeof q.name === 'string') {
    person.selectPersonById({
      name_id: q.name_id,
      name: q.name,
      primary_profession: null,
      title_count: 0,
    })
  }
})
```

`title_count: 0` is acceptable as a placeholder — the value is only displayed
inside the autocomplete item list, which is not shown when the store is
pre-seeded. Once `fetchTitles()` resolves, the header will use
`person.personResults.total` for the count.

## Anti-patterns

- Do NOT skip `selectPerson()` and write to `selectedPerson.value` directly — the
  existing helper also clears `personResults` and `error`, which we want to
  preserve on deep-link entry.
- Do NOT re-run the mount handler on every query change; use `onMounted`, not a
  `watch` on the query.
- Do NOT pass `primary_profession: undefined`; Pinia state should be stable and
  the type explicitly allows `null`.

## Post-conditions

```bash
grep -n "selectPersonById" frontend/app/stores/person.ts
# Expected: definition + return entry
```

```bash
grep -n "useRoute" frontend/app/pages/person.vue
# Expected: at least 1 match
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

Manual smoke test (after ST-004 lands): navigate to
`/person?name_id=christopher%20nolan&name=Christopher%20Nolan` and verify the
person page loads titles for that name.

## Files Changed

```
frontend/app/stores/person.ts
frontend/app/pages/person.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: person page deep-link support via query params (ST-002)
```
