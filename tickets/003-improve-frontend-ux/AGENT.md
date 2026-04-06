# Agent Instructions — Ticket 003

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Done** — All subtasks complete. No agent action needed.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order:

```
ST-001  ← redesign filter panel (no deps)
ST-002  ← per-category count controls (no deps)
ST-003  ← improve date range selector (depends on ST-001)
ST-004  ← dismissed page titles (no deps)
ST-005  ← card layout and region (no deps)
ST-006  ← visual design overhaul (depends on ST-001, ST-005)
ST-007  ← auto-apply filters with debounce (depends on ST-001)
```

## Ticket-Specific Context

- Frontend uses Nuxt 4 + Vuetify 4
- All changes are in `frontend/app/` — no backend changes
- Type-check with `cd frontend && npx nuxt typecheck`
