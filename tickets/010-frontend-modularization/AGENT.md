# Ticket 010 — Agent Execution Guide

## Execution Order

1. **ST-001** → Extract ActionsBar (actions + data source panel)
2. **ST-002** → Extract ActiveFilterSummary (filter chips)
3. **ST-003** → Extract CategoryTabs (tab bar)
4. **ST-004** → Extract RecommendationGrid (grid + states + CSS)
5. **ST-005** → FilterDrawer slots (independent, can run any time)
6. **ST-006** → CardDisplayItem interface (independent, can run any time)

ST-001 through ST-004 must run in order — each extraction starts from the result of
the previous one.

ST-005 and ST-006 have no dependencies and can run at any point.

## Key Principle

These are **pure extraction refactors**. No functional changes, no new features, no
visual changes. The UI must look and behave identically after each subtask.

## Verification

After each subtask, run:
```bash
cd frontend && npx nuxt typecheck
```

After all subtasks, verify `index.vue` is under 80 lines:
```bash
wc -l frontend/app/pages/index.vue
```
