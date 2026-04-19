---
id: "021"
title: "FTS5 full-text search for people and title search"
status: open
priority: high
component: backend
files_affected:
  - app/services/scored_store.py
  - app/api/routes.py
  - app/models/schemas.py
  - frontend/app/stores/person.ts
  - frontend/app/stores/similar.ts
  - frontend/app/pages/person.vue
  - frontend/app/pages/similar.vue
---

# TICKET-021: FTS5 Full-Text Search for People and Title Search

---

## Summary

Both `search_people()` and `search_titles()` in `scored_store.py` use `LIKE '%query%'`
which forces a full table scan on every keystroke. For the people search this is
compounded by a 3-table JOIN with GROUP BY and COUNT(DISTINCT), making it noticeably
slow on the full IMDB dataset (~1M people, ~600K scored candidates).

Replace both search paths with SQLite FTS5 virtual tables for near-instant lookup, and
denormalize `title_count` / `rated_count` onto the `people` table to eliminate the
expensive JOIN at query time.

## Current Bottlenecks

### People search (`search_people`)
1. `LIKE '%query%'` on `people.name` — no index, full table scan of ~1M rows
2. JOIN to `title_people` + LEFT JOIN to `rated_titles` + GROUP BY + COUNT(DISTINCT) for
   every matching row
3. No index on `people.name`

### Title search (`search_titles`)
1. `LIKE '%query%'` on both `rated_titles.title` and `scored_candidates.title` — full
   table scans on ~600K+ rows
2. UNION of two scans doubles the work

## Priority Breakdown

| Priority | Count |
|---|---|
| High | 1 |
| Medium | 2 |
| Low | 1 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](021-fts5-search-performance/ST-001-denormalize-people-counts.md) | Denormalize title_count and rated_count onto people table | Medium | Open |
| [ST-002](021-fts5-search-performance/ST-002-fts5-people-search.md) | Add FTS5 virtual table for people name search | High | Open |
| [ST-003](021-fts5-search-performance/ST-003-fts5-title-search.md) | Add FTS5 virtual table for title search | Medium | Open |
| [ST-004](021-fts5-search-performance/ST-004-frontend-search-ux.md) | Frontend: reduce debounce and improve search responsiveness | Low | Open |

## Context

### Why FTS5 over alternatives

- **In-memory cache**: Similar speed at this scale, but FTS5 gives word-boundary matching
  for free and doesn't require manual cache invalidation logic.
- **Elasticsearch/Redis**: Overkill for a single-user app — adds JVM/service dependency,
  Docker complexity, and ~500MB+ RAM overhead for no practical benefit at this scale.
- **LIKE with B-tree index**: Leading `%` wildcard prevents index use. Prefix-only search
  (`LIKE 'query%'`) would use an index but doesn't support searching by last name.

FTS5 is zero-dependency (built into SQLite), supports prefix queries (`MATCH 'scor*'`),
and the migration surface to Elasticsearch later is just 2-3 functions in `scored_store.py`.

### How FTS5 works here

- External content tables (`content=people`, `content=scored_candidates`) avoid data
  duplication — the FTS index references the existing tables.
- FTS tables are populated during `save_people()` and `save_scored_candidates()` —
  the same write path that already exists.
- `MATCH` queries replace `LIKE` — e.g. `WHERE people_fts MATCH 'scorsese*'` instead of
  `WHERE p.name LIKE '%scorsese%'`.
- Word-boundary matching: searching "new" will match "Paul Newman" (word prefix) but not
  "Renewed". This is the expected UX for name search.

### Migration path

If FTS5 is ever insufficient, swapping to Elasticsearch requires changing only:
1. `search_people()` — replace SQL with ES client call
2. `search_titles()` — replace SQL with ES client call
3. The FTS table creation in `_ensure_tables()` — remove
No route, store, or frontend changes needed.

## Files in Scope

- `app/services/scored_store.py` — FTS5 tables, rewrite search functions, denormalize counts
- `app/api/routes.py` — no structural changes expected, but may need minor adjustments
- `frontend/app/stores/person.ts` — reduce debounce if search is fast enough
- `frontend/app/stores/similar.ts` — reduce debounce if search is fast enough
- `frontend/app/pages/person.vue` — reduce debounce delay
- `frontend/app/pages/similar.vue` — reduce debounce delay

## Acceptance Criteria

- [ ] People search returns results in < 50ms on the full IMDB dataset
- [ ] Title search returns results in < 50ms on the full IMDB dataset
- [ ] FTS5 tables are created and populated during the existing save paths
- [ ] Prefix queries work (typing "scor" finds "Martin Scorsese")
- [ ] Results are still ranked by rated_count DESC, then title_count DESC (people)
- [ ] Results are still ranked by is_rated DESC, then num_votes DESC (titles)
- [ ] Frontend debounce is reduced to reflect faster backend response
- [ ] All existing tests pass
- [ ] Lint passes: `uv run ruff check app/` and `cd frontend && npx nuxt typecheck`

## Scope Fence

- Do not add Elasticsearch, Redis, or any external service
- Do not change the API response schemas — only the search implementation
- Do not change the similar-titles cosine similarity engine (only the title *search* input)
- Do not modify the pipeline or scoring logic
