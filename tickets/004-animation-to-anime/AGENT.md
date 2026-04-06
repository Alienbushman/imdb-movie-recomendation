# Agent Instructions — Ticket 004

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Done** — All subtasks complete. No agent action needed.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order (strictly sequential):

```
ST-001  ← add is_anime flag using Fribb whitelist (no deps)
ST-002  ← rename backend animation → anime (depends on ST-001)
ST-003  ← rename frontend animation → anime (depends on ST-002)
```

## Ticket-Specific Context

- The Fribb anime title ID whitelist is fetched from GitHub at pipeline time
- `is_anime` flag on `CandidateTitle` drives the anime tab filtering
- Renaming touches both backend schemas and frontend types — must be coordinated
