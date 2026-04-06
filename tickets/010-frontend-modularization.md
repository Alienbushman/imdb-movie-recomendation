---
id: "010"
title: "Frontend Component Modularization"
status: done
priority: medium
component: frontend
files_affected:
  - frontend/app/pages/index.vue
  - frontend/app/components/FilterDrawer.vue
  - frontend/app/components/RecommendationCard.vue
  - frontend/app/types/index.ts
---

# TICKET-010: Frontend Component Modularization

---

## Problem

`index.vue` is a 260-line monolith containing 10 unrelated concerns: action buttons,
data source inputs, filter summary chips, loading states, category tabs, empty state,
card grid, grid CSS, and multiple event handlers. Multiple open tickets need to modify
it, creating a high risk of merge conflicts when agents work in parallel.

**Current file-collision map** (file → open tickets that modify it):

```
pages/index.vue              → T006, T008-ST1, T008-ST2, T008-ST3
stores/recommendations.ts    → T006, T008-ST1
components/RecommendationCard.vue → T009-ST4
components/FilterDrawer.vue  → T009-ST4
types/index.ts               → T008-ST1, T009-ST3
```

The worst hotspot is `index.vue` — four subtasks across two tickets all need to edit
the same file. T008's three subtasks (sort controls, scroll-to-top, grid density) all
target the card grid area, while T006 (fast initial load) targets the mount/load logic.

---

## Solution

Extract cohesive sections from `index.vue` into focused components so that future
tickets modify isolated files instead of the same monolith. Also define a shared card
data interface in `types/index.ts` so `RecommendationCard.vue` can serve both the
recommendations and similar-titles pages without prop-type changes.

### Target state after refactoring

```
pages/index.vue              ← slim orchestrator (~50 lines): imports + layout only
components/ActionsBar.vue    ← Generate/Retrain buttons, data source panel, chips
components/ActiveFilterSummary.vue ← filter/exclusion chip bar
components/CategoryTabs.vue  ← tab bar with badge counts
components/RecommendationGrid.vue  ← empty state, skeletons, card grid, grid CSS,
                                     scroll-to-top anchor, sort/density bar area
components/FilterDrawer.vue  ← unchanged, but with named slots for page-specific sections
components/RecommendationCard.vue ← accepts CardDisplayItem union type
```

### Collision map after refactoring

```
pages/index.vue              → T006 only (one-line onMounted change)
components/RecommendationGrid.vue → T008-ST1, T008-ST2, T008-ST3
components/RecommendationCard.vue → (no ticket — T009-ST4 uses shared interface)
components/FilterDrawer.vue  → (no ticket — T009-ST4 uses slot)
types/index.ts               → T008-ST1, T009-ST3 (unchanged, but types are additive)
```

The key win: **T006 and T008 no longer collide on any file.**

---

## Subtasks

| # | File | Title | Effort |
|---|------|-------|--------|
| 1 | [ST-001-extract-actions-bar.md](010-frontend-modularization/ST-001-extract-actions-bar.md) | Extract ActionsBar component | Low |
| 2 | [ST-002-extract-filter-summary.md](010-frontend-modularization/ST-002-extract-filter-summary.md) | Extract ActiveFilterSummary component | Low |
| 3 | [ST-003-extract-category-tabs.md](010-frontend-modularization/ST-003-extract-category-tabs.md) | Extract CategoryTabs component | Low |
| 4 | [ST-004-extract-recommendation-grid.md](010-frontend-modularization/ST-004-extract-recommendation-grid.md) | Extract RecommendationGrid component | Low-Medium |
| 5 | [ST-005-filter-drawer-slots.md](010-frontend-modularization/ST-005-filter-drawer-slots.md) | Add slots to FilterDrawer for page-specific sections | Low |
| 6 | [ST-006-shared-card-interface.md](010-frontend-modularization/ST-006-shared-card-interface.md) | Define CardDisplayItem union type for RecommendationCard | Low |

### Execution Order

```
Subtasks 1–4 are sequential (each shrinks index.vue, so the next extraction starts
from the result of the previous one).

Subtasks 5 and 6 are independent of 1–4 and of each other — can run in parallel
with any of the others.
```

### Dependency: Run Before Other Frontend Tickets

This ticket should be completed before T008 and T009 frontend subtasks begin. T006
can proceed in parallel (its changes are compatible with this refactoring).

---

## Acceptance Criteria

- [ ] `index.vue` is under 80 lines of template (currently ~200 lines of template)
- [ ] `index.vue` imports and composes the extracted components — no logic duplication
- [ ] All extracted components are purely presentational or use props/emits/stores — no
      new API calls or business logic introduced
- [ ] `FilterDrawer.vue` exposes a named slot for page-specific filter sections
- [ ] `RecommendationCard.vue` accepts `CardDisplayItem` (union of `Recommendation`
      and future `SimilarTitle`) without `as any` casts
- [ ] No functional or visual changes — the UI looks and behaves identically
- [ ] Lint passes: `cd frontend && npx nuxt typecheck`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`
- [ ] All existing `data-e2e` attributes are preserved on the same elements
