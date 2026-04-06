---
ticket: "002"
subtask: 5
title: "Frontend: Update API Composable"
status: open
effort: low
component: frontend
depends_on: []
files_modified:
  - frontend/app/composables/useApi.ts
files_created: []
---

# SUBTASK 05: Frontend — Update API Composable

---

## Objective

Update the `getRecommendations` function in `useApi.ts` to accept and forward an optional `imdbUrl` parameter as a query string on the `POST /recommendations` call.

## Context

Read `frontend/app/composables/useApi.ts` before making changes to understand the exact current signature and query-building logic of `getRecommendations`. The composable builds a query object and calls `POST /api/v1/recommendations` — the `imdb_url` parameter needs to be appended to this query when provided.

Note the naming convention: frontend uses camelCase (`imdbUrl`) while the backend query param is snake_case (`imdb_url`).

## Implementation

### 1. Update `getRecommendations` signature

Add an optional `imdbUrl` parameter:

```typescript
async function getRecommendations(
  filters?: RecommendationFilters,
  retrain = false,
  imdbUrl?: string,
): Promise<RecommendationResponse>
```

### 2. Add `imdb_url` to the query object

In the query-building section, add:

```typescript
if (imdbUrl) {
  query.imdb_url = imdbUrl
}
```

### 3. No other changes

The rest of the composable (filter mapping, response handling, error handling) remains unchanged.

## Acceptance Criteria

- [ ] `getRecommendations(filters, false, 'https://www.imdb.com/user/ur38228117/ratings/')` sends `?imdb_url=...` in the request
- [ ] `getRecommendations()` (no URL) sends request without `imdb_url` param — existing behavior preserved
- [ ] `imdbUrl` is typed as `string | undefined`
- [ ] Existing filter and retrain params unchanged

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
