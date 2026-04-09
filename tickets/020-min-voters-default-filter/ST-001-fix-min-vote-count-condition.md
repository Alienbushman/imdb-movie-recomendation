---
id: ST-001
ticket: "020"
title: "Fix min_vote_count always sent when non-zero"
priority: Medium
risk: low
status: Done
dependencies: []
subsystems: [frontend]
---

# ST-001 — Fix min_vote_count always sent when non-zero

**Priority:** Medium
**Risk:** Low
**Files:** `frontend/app/stores/filters.ts`

## Problem

In `buildFilters()` (`frontend/app/stores/filters.ts`, line 88), the condition for including
`min_vote_count` in the request payload is:

```typescript
if (minVoteCount.value > FILTER_DEFAULTS.minVoteCount) f.min_vote_count = minVoteCount.value
```

`FILTER_DEFAULTS.minVoteCount` is `1000`. Because the condition uses strict `>`, the default
value of `1000` is **never** included. On initial page load the backend receives no
`min_vote_count` parameter and applies its own default, which may differ from what the
slider shows.

The correct omission rule is: skip the field only when the value is `<= 0` (meaning "no
restriction"). Any positive value — including the default 1000 — must be forwarded.

## Fix

1. Open `frontend/app/stores/filters.ts`
2. Find the line (currently line 88):
   ```typescript
   if (minVoteCount.value > FILTER_DEFAULTS.minVoteCount) f.min_vote_count = minVoteCount.value
   ```
3. Replace with:
   ```typescript
   if (minVoteCount.value > 0) f.min_vote_count = minVoteCount.value
   ```

That is the only change required.

## Anti-patterns

- Do NOT change `FILTER_DEFAULTS.minVoteCount` — the default value is correct, only the
  send condition is wrong.
- Do NOT apply the same change to `minImdbRating` or `maxRuntime` — their omission
  semantics are intentionally different (0 and 300 genuinely mean "no restriction").
- Do NOT touch `hasActiveFilters` or `activeFilterSummary` — they correctly treat any
  value `> 1000` as "active." The filter is now always sent, but it is only highlighted
  as an active override when the user moves the slider above the default.

## Post-conditions

```bash
# Confirm the old pattern is gone
grep -n "FILTER_DEFAULTS.minVoteCount" frontend/app/stores/filters.ts
# Expected: only the FILTER_DEFAULTS definition and hasActiveFilters/activeFilterSummary lines
# The buildFilters() line should NOT appear
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/stores/filters.ts
```

## Commit Message

```
fix: always send min_vote_count filter even at default value
```

## Gotchas

None — single-line change, zero backend impact.
