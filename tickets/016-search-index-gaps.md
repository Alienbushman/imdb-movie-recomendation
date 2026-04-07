---
id: "016"
title: "Search and browse index gaps"
status: open
priority: high
component: backend
files_affected:
  - app/services/pipeline.py
  - app/services/scored_store.py
  - app/api/routes.py
---

# Ticket 016 — Search and Browse Index Gaps

## Problem

Two search features silently fail to find well-known titles and people:

1. **Person search** (`/people/search`) — The `people` and `title_people` tables are
   populated only from unrated candidate titles. If a director (e.g. Martin Scorsese)
   has famous films that the user has already rated, he may have zero rows in
   `title_people` and is filtered out by the `JOIN` in `search_people`. Result: the
   more films you've rated from a director, the less likely they are to appear in search.

2. **Title search** (`/search`) — `search_titles` queries only `scored_candidates`.
   Rated titles (e.g. Con Air, if the user has rated it) are only found via
   `_state["titles"]` — an in-memory list that is reset on every server restart.
   After a restart (without re-running the pipeline), rated titles are completely
   unsearchable.

## Root causes

- `people`/`title_people` build loop in `pipeline.py` iterates `scored_candidates`
  only; `titles` (the rated watchlist) is available in the same scope but ignored.
- `search_titles` in `scored_store.py` has no fallback to a persisted rated-titles
  store; the server-restart survival path relies on the volatile `_state` dict.

## Subtasks

| ID | Title | Status |
|----|-------|--------|
| ST-001 | Index directors from rated titles in people table | Open |
| ST-002 | Persist rated titles to SQLite for durable title search | Open |
