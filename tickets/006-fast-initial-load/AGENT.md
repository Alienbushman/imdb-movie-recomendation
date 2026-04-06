# Agent Instructions — Ticket 006

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

---

## Subtask Order

Subtasks are independent — can run in parallel:

```
ST-001  ← frontend: try fast path on mount (no deps)
ST-002  ← backend: skip rescore when DB fresh (no deps)
```

## Ticket-Specific Context

- The "fast path" is `POST /recommendations/filter` — queries SQLite directly, < 1 second
- The "full path" is `POST /recommendations` — runs all 4 pipeline steps, tens of seconds
- `scored_candidates.db` must exist and have rows for the fast path to work
- A 409 response from the filter endpoint means no cached scores exist
- `pipelineReady` in the Pinia store must be persisted to `localStorage` for the fast path
  to be used on hard reload (install `@pinia-plugin-persistedstate/nuxt`)
- The `force` query parameter on `POST /recommendations` bypasses the backend skip guard
- "Generate" and "Retrain" buttons must always trigger the full pipeline — no change
