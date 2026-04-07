# Agent Instructions — Ticket 014

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for execution.

---

## Goal

Bring all project documentation into sync with the current codebase. No runtime code
changes — this ticket is documentation and docstrings only (plus `frontend/README.md`).

---

## Subtask Order

```
ST-001  ← fix CLAUDE.md endpoint table + architecture list (no deps)
ST-002  ← rewrite frontend/README.md (no deps, can run in parallel with ST-001)
ST-003  ← add module-level docstrings to 4 service files (no deps)
ST-004  ← document startup sequence in CLAUDE.md (depends on ST-001)
```

ST-001, ST-002, and ST-003 have no dependencies and can be done in any order.
ST-004 extends CLAUDE.md so it should come after ST-001 to avoid merge conflicts.

---

## Ticket-Specific Context

### What changed and when

| Gap | Root cause |
|---|---|
| Missing endpoints in CLAUDE.md | Tickets 009 (similar), 011 (person browse), and an incremental filter endpoint were never added to the doc table |
| Missing `similar.py` service | Ticket 009 added the service but the architecture doc wasn't updated |
| Frontend README is boilerplate | `frontend/README.md` was never replaced after project bootstrap |
| Missing module docstrings | Services grew large across many tickets; docstrings were never backfilled |

### Lint scope

Only `app/services/*.py` changes need lint. `uv run ruff check app/` must pass with zero
new warnings. Adding docstrings does not introduce N806 issues, but watch for line-length
violations in long docstrings (max 88 chars per line — ruff default).

### No cache invalidation needed

This ticket touches only documentation and docstrings. No changes to `CandidateTitle`,
`FeatureVector`, model training, or database schema. No cache files need to be deleted.

### Frontend typecheck

No `.vue` or `.ts` files are modified (only `frontend/README.md`). Skipping
`npx nuxt typecheck` is acceptable, but running it is safe and welcome.
