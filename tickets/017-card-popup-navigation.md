---
id: "017"
title: "Card Popup Navigation: Find Similar + Click Person"
status: done
priority: medium
component: frontend
files_affected:
  - frontend/app/components/RecommendationCard.vue
  - frontend/app/pages/similar.vue
  - frontend/app/pages/person.vue
  - frontend/app/stores/similar.ts
  - frontend/app/stores/person.ts
---

# TICKET-017: Card Popup Navigation — Find Similar + Click Person

---

## Summary

When a user opens the detail dialog on a recommendation/similar/person card, they
should be able to:

1. Click a **Find Similar** button to jump to the Find Similar page seeded with
   this title.
2. Click the director or any actor name to jump to the Browse by Person page
   showing that person's filmography.

Both jumps must be deep-linkable via URL query params so reload works and the
origin card does not need to pass data via component props.

## Priority Breakdown

| Priority | Count |
|---|---|
| High | 0 |
| Medium | 4 |
| Low | 0 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](017-card-popup-navigation/ST-001-similar-deep-link.md) | Similar page deep-link support | Medium | Done |
| [ST-002](017-card-popup-navigation/ST-002-person-deep-link.md) | Person page deep-link support | Medium | Done |
| [ST-003](017-card-popup-navigation/ST-003-find-similar-button.md) | Find Similar button in card popup | Medium | Done |
| [ST-004](017-card-popup-navigation/ST-004-clickable-person-chips.md) | Clickable director/actor chips in card popup | Medium | Done |

## Context

- The card detail dialog lives in [RecommendationCard.vue](../frontend/app/components/RecommendationCard.vue)
  (the `<v-dialog>` block starting around line 202). Today it shows director and
  cast as plain joined text and has two action buttons: **View on IMDB** and **Dismiss**.
- The `/similar` page ([similar.vue](../frontend/app/pages/similar.vue)) drives
  the similarity engine via `useSimilarStore()`. Its seed is a full
  `TitleSearchResult` populated from the autocomplete. The store's
  `fetchSimilar()` only needs `selectedSeed.imdb_id`, so a minimal seed object
  (`{ imdb_id, title, year, title_type, is_rated: false }`) built from URL query
  params is sufficient to bootstrap the page.
- The `/person` page ([person.vue](../frontend/app/pages/person.vue)) drives the
  Browse-by-Person feature via `usePersonStore()`. Its selection is a
  `PersonSearchResult` populated from the autocomplete. The store's
  `fetchTitles()` only uses `selectedPerson.name_id`, so a minimal selection
  object (`{ name_id, name, primary_profession: null, title_count: 0 }`) is
  sufficient to bootstrap the page.
- **`name_id` is deterministic**: per
  [pipeline.py:166](../app/services/pipeline.py#L166) the backend uses
  `name.lower()` as the `name_id` when populating the `people` table. This means
  the frontend can compute a valid `name_id` from any actor/director display
  name without a server round-trip — no new backend endpoint is required for
  this ticket.
- `CardDisplayItem` already carries all the data we need (`title`, `year`,
  `title_type`, `imdb_id`, `director`, `actors`), so no schema changes.

## Files in Scope

- `frontend/app/components/RecommendationCard.vue`
- `frontend/app/pages/similar.vue`
- `frontend/app/pages/person.vue`
- `frontend/app/stores/similar.ts`
- `frontend/app/stores/person.ts`

## Acceptance Criteria

- [ ] Opening a card dialog shows a **Find Similar** button in the action row
      (unless the card has no `imdb_id`, in which case it is hidden).
- [ ] Clicking **Find Similar** navigates to `/similar?imdb_id=...&title=...&year=...&title_type=...`
      and the similar page loads results immediately for that seed.
- [ ] In the dialog, the director is rendered as a single clickable chip (not plain text).
- [ ] In the dialog, each actor is rendered as its own clickable chip (not a comma-joined string).
- [ ] Clicking a director or actor chip navigates to `/person?name_id=...&name=...`
      and the person page loads that person's titles immediately.
- [ ] Reloading the browser on either deep-link URL still shows the correct seeded results.
- [ ] `cd frontend && npx nuxt typecheck` passes with zero new errors.
- [ ] `uv run pytest tests/ -q` still passes (frontend-only changes, so no regressions expected).

## Scope Fence

- Only modify files listed in each subtask's "Files Changed" section.
- Do not change backend schemas, endpoints, or the scored DB.
- Do not reshape the `CardDisplayItem` type or the `toCardItem` / `toSimilarCardItem` /
  `toPersonCardItem` helpers. They already carry everything we need.
- Do not add new dependencies or install packages.
