---
id: "018"
title: "Person browse shows all titles (rated + unrated)"
status: open
priority: high
component: full_stack
files_affected:
  - app/services/candidates.py
  - app/services/pipeline.py
  - app/services/scored_store.py
  - app/models/schemas.py
  - app/api/routes.py
  - frontend/app/types/index.ts
  - frontend/app/pages/person.vue
---

# TICKET-018: Person Browse Shows All Titles (Rated + Unrated)

---

## Summary

When browsing by person (e.g. Paul Newman), only unrated/unseen candidate titles
appear. Rated titles — films the user has already watched — are invisible because
`query_titles_by_person` only JOINs `scored_candidates`, which excludes every title
the user has rated. The fix has three parts: (1) index actor/writer crew from rated
titles in `title_people` so they can be queried, (2) enrich the `rated_titles` table
with display metadata and UNION it into the person query, and (3) add a
seen/unseen toggle on the frontend so the user can show or hide films they've
already watched.

## Priority Breakdown

| Priority | Count |
|---|---|
| High | 2 |
| Medium | 1 |
| Low | 0 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](018-person-browse-all-titles/ST-001-index-rated-crew.md) | Index actor/writer/composer crew from rated titles in title_people | High | Open |
| [ST-002](018-person-browse-all-titles/ST-002-union-rated-titles.md) | Enrich rated_titles table and UNION into query_titles_by_person | High | Open |
| [ST-003](018-person-browse-all-titles/ST-003-frontend-seen-filter.md) | Frontend: seen/unseen toggle + seen badge on person browse | Medium | Open |

## Context

### Why rated titles are missing

`scored_candidates` only contains titles the user has **not** rated (`seen_ids` is
passed as an exclusion set in `load_candidates_from_datasets`). The person browse
endpoint (`GET /people/{name_id}`) JOINs `title_people` with `scored_candidates`, so
any film the user has seen is invisible regardless of whether the person appears in it.

### Why ticket 016 didn't fix this

Ticket 016 ST-001 added directors from rated titles to `title_people`. This helps
directors appear in person search. But:

1. It only indexed **directors**, not actors/writers/composers/cinematographers. An
   actor like Paul Newman has no `title_people` rows for his rated films.
2. Even for directors, clicking through shows 0 results because `query_titles_by_person`
   only queries `scored_candidates` — the rated films aren't in that table.

### Data available for rated titles

`RatedTitle` (from the IMDB CSV export) has: `directors`, `writers`, `imdb_rating`,
`num_votes`, `runtime_mins`, `year`, `genres`, `language`, `user_rating`.

Actors, composers, and cinematographers for rated titles are loaded from the IMDB
dataset files during `load_candidates_from_datasets`. They are returned as
`rated_actors`, `rated_composers`, `rated_cinematographers` on full rebuilds, but
are `None` on cache hits.

## Files in Scope

- `app/services/candidates.py` — new `load_crew_for_titles()` helper
- `app/services/pipeline.py` — index all crew roles from rated titles
- `app/services/scored_store.py` — schema migration + enriched write + UNION query
- `app/models/schemas.py` — add `is_rated` to `PersonTitleResult`
- `app/api/routes.py` — pass `is_rated` when constructing `PersonTitleResult`
- `frontend/app/types/index.ts` — add `is_rated` to type + badge in `toPersonCardItem`
- `frontend/app/pages/person.vue` — seen/unseen toggle

## Acceptance Criteria

- [ ] Searching Paul Newman (or any actor whose filmography is mostly rated) and
      clicking their name shows both rated and unrated titles
- [ ] Rated titles display a "Seen" badge in the card
- [ ] A seen/unseen toggle on the person browse page lets the user filter to
      unseen-only, seen-only, or all titles
- [ ] The existing role filter (director / actor / writer / any) still works
- [ ] `uv run ruff check app/` and `uv run pytest tests/ -q` pass
- [ ] `cd frontend && npx nuxt typecheck` passes

## Scope Fence

- Do not rescore rated titles — `predicted_score` for rated rows uses the user's own
  rating (`user_rating` from the IMDB CSV) as a stand-in
- Do not modify `query_candidates` (the recommendation endpoint) — rated titles
  should not appear in the main recommendations view
- Do not touch `similar.py` or the `/similar` endpoint
- The `rated_titles` schema migration must be additive (ALTER TABLE ADD COLUMN) so
  existing databases do not need to be deleted
