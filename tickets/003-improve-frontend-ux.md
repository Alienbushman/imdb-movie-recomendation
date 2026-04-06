---
id: "003"
title: "Improve Frontend UX and Visual Design"
status: done
priority: high
component: full_stack
files_affected:
  - frontend/app/pages/index.vue
  - frontend/app/pages/dismissed.vue
  - frontend/app/components/RecommendationCard.vue
  - frontend/app/stores/filters.ts
  - frontend/app/stores/recommendations.ts
  - frontend/app/layouts/default.vue
  - frontend/app/types/index.ts
  - frontend/app/composables/useApi.ts
  - frontend/nuxt.config.ts
  - app/api/routes.py
  - app/models/schemas.py
  - app/services/recommend.py
---

# TICKET-003: Improve Frontend UX and Visual Design

---

## Summary

User feedback identifies six areas where the frontend UX falls short of expectations. The site is functional but feels unpolished — filters are buried in a hidden drawer that requires manual "Apply" clicks, the date range controls are raw number inputs, dismissed titles show only opaque IMDB IDs, card spacing is inconsistent, there's no way to control how many results appear per category, the region/country isn't visible on cards, and the overall visual design uses unstyled Vuetify defaults.

This ticket addresses all six feedback areas plus a region display enhancement across seven subtasks.

## User Feedback

1. **Filters feel unnatural** — Hidden in a slide-out drawer, require explicit "Apply" click, no search within long lists (23 genres, 29 languages), no visual grouping
2. **No per-category count control** — `top_n` per category is hardcoded in `config.yaml` (20 movies, 10 series, 10 animation) with no UI to adjust
3. **Date range is unintuitive** — Two raw `<input type="number">` fields; no presets, no visual range indicator
4. **Dismissed page has no titles** — Only shows raw IMDB IDs (e.g. `tt1375666`), no title, year, or metadata
5. **Card spacing/layout issues** — Cards vary wildly in height, no consistent visual rhythm, could improve information density
6. **Site lacks visual polish** — Default Vuetify dark theme, no custom colors, no hover effects, no loading skeletons, no visual hierarchy
7. **Region not visible on cards** — `country_code` exists on `Recommendation` but isn't displayed; users want to see where a movie/series is from

## Current Architecture

### Filter System
- Filters live in a `v-navigation-drawer` (right side, `width="350"`, `temporary`) toggled by a "Filters" button
- All filter changes require clicking "Apply Filters" to take effect
- Year range: two `v-text-field type="number"` with `clearable`
- Genres: full 23-chip `v-chip-group` for include AND another 23-chip group for exclude
- Languages: `v-autocomplete` for include, full 29-chip `v-chip-group` for exclude
- Sliders for min IMDB rating, max runtime, min predicted score
- Filter state managed in `stores/filters.ts`

### Card Grid
- `v-row` with `v-col cols="12" sm="6" md="4" lg="3"` — responsive 1-4 columns
- `RecommendationCard.vue` uses `height="100%"` on `v-card` with `d-flex flex-column`
- No max-height, no content truncation, no uniform sizing

### Dismissed Page
- `GET /dismissed` returns `{ dismissed_ids: string[], count: number }` — IDs only
- Frontend renders a `v-list` with each ID as a link to IMDB, no metadata resolution

### Result Counts
- `config.yaml` defines `top_n_movies: 20`, `top_n_series: 10`, `top_n_animation: 10`
- Read in `recommend.py:build_recommendations_from_scored()` at lines 297-299
- Not exposed as API parameters — no way to change from the frontend

---

## Subtasks

All subtasks are in the [003-improve-frontend-ux/](003-improve-frontend-ux/) directory:

| # | Subtask | Effort | Component | Dependencies |
|---|---------|--------|-----------|-------------|
| 1 | [Redesign filter panel UX](003-improve-frontend-ux/ST-001-redesign-filter-panel.md) | Medium | Frontend | None |
| 2 | [Per-category result count controls](003-improve-frontend-ux/ST-002-per-category-count-controls.md) | Low-Medium | Full Stack | None |
| 3 | [Improve date range selector](003-improve-frontend-ux/ST-003-improve-date-range-selector.md) | Low | Frontend | Subtask 1 (filter panel context) |
| 4 | [Show title metadata on dismissed page](003-improve-frontend-ux/ST-004-dismissed-page-titles.md) | Low-Medium | Full Stack | None |
| 5 | [Fix card layout, spacing, and show region](003-improve-frontend-ux/ST-005-card-layout-and-region.md) | Low-Medium | Frontend | None |
| 6 | [Visual design overhaul](003-improve-frontend-ux/ST-006-visual-design-overhaul.md) | Medium-High | Frontend | Subtasks 1, 5 (styling builds on layout) |
| 7 | [Auto-apply filters with debounce](003-improve-frontend-ux/ST-007-auto-apply-filters.md) | Low | Frontend | Subtask 1 (filter panel must exist) |

### Execution Order

```
Phase 1 (parallel, no deps):  Subtasks 1, 2, 4, 5
Phase 2 (after subtask 1):    Subtasks 3, 7
Phase 3 (after subtasks 1+5): Subtask 6
```

Subtasks 1, 2, 4, and 5 have no mutual dependencies and can be executed in parallel.
Subtask 3 (date range) fits within the filter panel redesign from subtask 1.
Subtask 7 (auto-apply) depends on the filter panel from subtask 1 being in place.
Subtask 6 (visual overhaul) should run last as it applies theming on top of the layout changes from subtasks 1 and 5.

---

## Acceptance Criteria

- [ ] Filters are accessible without a hidden drawer — visible, grouped, and searchable
- [ ] Filters auto-apply on change (debounced) rather than requiring an explicit "Apply" button
- [ ] User can control how many results appear per category (movies, series, animation)
- [ ] Date range uses a visual range selector with decade presets
- [ ] Dismissed page shows title names, year, and type — not just IMDB IDs
- [ ] Cards have consistent heights, proper spacing, and display the country/region
- [ ] Overall visual design is polished with custom colors, hover effects, and loading states
