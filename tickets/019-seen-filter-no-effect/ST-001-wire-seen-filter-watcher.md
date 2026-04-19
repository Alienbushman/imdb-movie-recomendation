---
id: ST-001
ticket: "019"
title: "Wire seenFilter change into FilterDrawer's scheduleApply"
priority: Medium
risk: low
status: Open
dependencies: []
subsystems: [frontend]
---

# ST-001 — Wire seenFilter Change into FilterDrawer's scheduleApply

**Priority:** Medium
**Risk:** Low
**Files:** `frontend/app/components/FilterDrawer.vue`

## Problem

`FilterDrawer.vue` contains a `v-btn-toggle` (line 199) that writes directly to
`similar.seenFilter`. When the user clicks a button the ref mutates, but the
component's `watch` (line 131-148) only covers `filters.*` properties — it does not
include `similar.seenFilter`. As a result `scheduleApply()` is never called and the
results list on the `/similar` page does not update.

## Pre-conditions

```bash
# Confirm seenFilter is NOT in the existing watch
grep -n "seenFilter" frontend/app/components/FilterDrawer.vue
# Expected: matches only inside the template (v-btn-toggle) and resetAndApply — NOT inside the watch callback
```

## Fix

### Step 1 — Add a watcher for `similar.seenFilter` in `FilterDrawer.vue`

In [FilterDrawer.vue](../../frontend/app/components/FilterDrawer.vue), add a
second `watch` immediately after the existing filter watch (after line 148).
Only fire `scheduleApply()` when on the similar page:

```ts
watch(
  () => similar.seenFilter,
  () => {
    if (isSimilarPage.value) scheduleApply()
  },
)
```

No other changes are needed.

## Anti-patterns

- Do NOT merge this into the existing watch array — that watch is unconditional and
  covers the recommendations page too. `seenFilter` is only meaningful on the
  similar page, so keep it in its own conditional watcher.
- Do NOT add a separate debounce; `scheduleApply` already debounces at 400 ms.
- Do NOT touch the store, the page, or the API endpoint.

## Post-conditions

```bash
# Confirm the new watch is present
grep -n "seenFilter" frontend/app/components/FilterDrawer.vue
# Expected: matches in both the template AND a watch callback
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

Manual smoke test: open the Similar page, search for any title, then toggle
**Unseen Only** — the list should re-fetch and exclude rated titles.
Toggle back to **All** — full list returns.

## Files Changed

```
frontend/app/components/FilterDrawer.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
fix: wire seenFilter watcher in FilterDrawer so Seen Status re-fetches (ST-001)
```
