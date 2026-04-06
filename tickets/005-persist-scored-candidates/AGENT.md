# Agent Instructions — Ticket 005

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Done** — All subtasks complete. No agent action needed.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order:

```
ST-001  ← create SQLite scored store (no deps)
ST-002  ← pipeline integration — write + slim _state (depends on ST-001)
ST-003  ← route GET endpoints to DB (depends on ST-002)
ST-004  ← deduplicate name_lookup + cache check (no deps, independent)
```

## Ticket-Specific Context

- SQLite DB at `data/cache/scored_candidates.db` — delete to force rescore
- After pipeline run, `_state` holds only model + feature names + taste profile (~10 MB)
- Large collections (candidates, scored) are NOT retained in memory
- Dismissed IDs are excluded at query time in `scored_store.query_candidates()`
