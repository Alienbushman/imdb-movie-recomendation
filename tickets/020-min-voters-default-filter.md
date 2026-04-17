---
id: "020"
title: "min_vote_count default never sent on initial load"
status: open
priority: medium
component: frontend
files_affected:
  - frontend/app/stores/filters.ts
---

# TICKET-020: min_vote_count default never sent on initial load

---

## Summary

The filters store initialises `minVoteCount` to `1000`, but `buildFilters()` only includes
`min_vote_count` in the request payload when the value is **strictly greater than** the
default (`> FILTER_DEFAULTS.minVoteCount`). This means the default of 1000 is never sent
to the API, so on every initial page load the backend applies its own default (which may
differ) rather than the value shown in the UI. Users see the slider set to 1000 votes but
results may include titles with far fewer voters.

## Priority Breakdown

| Priority | Count |
|---|---|
| High | 0 |
| Medium | 1 |
| Low | 0 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](020-min-voters-default-filter/ST-001-fix-min-vote-count-condition.md) | Fix min_vote_count always sent when non-zero | Medium | Open |

## Context

`buildFilters()` in `frontend/app/stores/filters.ts` uses different omission semantics for each
filter:

- `minImdbRating` — omitted when `<= 0` (0 = no restriction), included otherwise
- `maxRuntime` — omitted when at max bound (300 = no restriction), included otherwise
- `minPredictedScore` — omitted only when it equals the default exactly
- `minVoteCount` — **omitted when `<= 1000`** — this means the default is never sent

The correct semantics for `minVoteCount` is: omit only when `<= 0` (zero = no restriction).
Any non-zero value, including the default 1000, should be sent so the backend enforces the
same threshold the UI shows.

## Files in Scope

- `frontend/app/stores/filters.ts`

## Acceptance Criteria

- [ ] On initial load, `buildFilters()` includes `min_vote_count: 1000` in the payload
- [ ] Setting the slider to 0 omits `min_vote_count` from the payload (no restriction)
- [ ] Setting the slider above 0 always sends the value
- [ ] Frontend typecheck passes with no new errors

## Scope Fence

- Only modify `buildFilters()` in `filters.ts`
- Do not change `FILTER_DEFAULTS`, `hasActiveFilters`, or `activeFilterSummary`
- Do not touch backend files
