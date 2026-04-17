---
id: "019"
title: "Seen filter has no effect on Similar page"
status: open
priority: medium
component: frontend
files_affected:
  - frontend/app/components/FilterDrawer.vue
---

# TICKET-019: Seen Filter Has No Effect on Similar Page

---

## Summary

On the `/similar` page, toggling the **Seen Status** filter (All / Unseen Only / Seen Only)
in the sidebar has no visible effect — the results list does not change.

The control correctly mutates `similar.seenFilter` in the store, and `fetchSimilar()`
does pass `seenFilter.value` to the API. But `applyFilters()` is never called after
the toggle because the `FilterDrawer` watch only covers `filters` store properties —
`similar.seenFilter` is not in its dependency list.

## Priority Breakdown

| Priority | Count |
|---|---|
| High | 0 |
| Medium | 1 |
| Low | 0 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](019-seen-filter-no-effect/ST-001-wire-seen-filter-watcher.md) | Wire seenFilter change into FilterDrawer's scheduleApply | Medium | Open |

## Context

- `FilterDrawer.vue` has a `v-btn-toggle` bound to `similar.seenFilter` rendered
  only on the similar page (line 199). When the user clicks a button, the ref
  changes — but nothing triggers a re-fetch.
- The `watch` in `FilterDrawer.vue` (line 131-148) observes only `filters.*`
  reactive values. `similar.seenFilter` is not watched, so `scheduleApply()` is
  never called.
- `similar.applyFilters()` already calls `fetchSimilar()` with the current
  `seenFilter.value`, so the API contract is correct — the watch is the only
  missing piece.
- The `resetAndApply` function (line 150-162) already resets `similar.seenFilter`
  and calls `similar.applyFilters()` correctly, showing the intended pattern.

## Files in Scope

- `frontend/app/components/FilterDrawer.vue`

## Acceptance Criteria

- [ ] Toggling Seen Status to **Unseen Only** on the Similar page immediately
      re-fetches and shows only titles not in the user's rated list.
- [ ] Toggling to **Seen Only** shows only titles that are in the rated list.
- [ ] Toggling back to **All** shows the full result set.
- [ ] No other filter behaviour changes (recommendations page, person page unaffected).
- [ ] `cd frontend && npx nuxt typecheck` passes with zero new errors.

## Scope Fence

- Only `FilterDrawer.vue` changes. Do not touch the store, the page, or the API.
- Do not add a new debounce for `seenFilter`; re-use the existing `scheduleApply`.
