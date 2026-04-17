---
id: ST-004
ticket: "021"
title: "Frontend: reduce debounce and improve search responsiveness"
priority: Low
risk: zero
status: Open
dependencies: [ST-002, ST-003]
subsystems: [frontend]
---

# ST-004 — Frontend: Reduce Debounce and Improve Search Responsiveness

**Priority:** Low
**Risk:** Zero
**Files:** `frontend/app/pages/person.vue`, `frontend/app/pages/similar.vue`

## Problem

Both the person search and the similar-page title search use a 300ms debounce before
sending the search request. With FTS5 on the backend, search responses are now fast
enough (~5-10ms) that the debounce can be reduced for a snappier feel.

## Pre-conditions

```bash
# ST-002 and ST-003 must be done
grep "people_fts\|scored_candidates_fts" app/services/scored_store.py
# Expected: FTS5 tables present and used in search functions
```

## Fix

### Step 1 — Reduce debounce on person page

In `frontend/app/pages/person.vue`, reduce the debounce from 300ms to 150ms:

```ts
_searchTimer = setTimeout(() => {
  person.search(query)
}, 150)
```

### Step 2 — Reduce debounce on similar page

In `frontend/app/pages/similar.vue`, find the equivalent debounce timer and reduce
from 300ms to 150ms.

### Step 3 — Verify minimum query length

Both search paths already require `min_length=2` on the backend. Confirm the frontend
also enforces this (the person store checks `query.length < 2`). No change needed if
already in place.

## Anti-patterns

- Do NOT remove the debounce entirely — even with fast search, rapid keystroke events
  should be batched to avoid unnecessary network requests.
- Do NOT go below 100ms — at that point you're sending a request per keystroke on fast
  typists, which wastes bandwidth for no perceptible UX gain.
- Do NOT change the search API contract or add new parameters.

## Post-conditions

```bash
# Confirm reduced debounce values
grep -n "setTimeout" frontend/app/pages/person.vue frontend/app/pages/similar.vue
# Expected: 150ms (or similar reduced value) in both files
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

Manual smoke test: type a search query on both pages — results should appear
noticeably faster than before.

## Files Changed

```
frontend/app/pages/person.vue
frontend/app/pages/similar.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
perf: reduce search debounce to 150ms now that FTS5 is fast (ST-004)
```
