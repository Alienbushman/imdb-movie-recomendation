# Agent Instructions — Ticket 001

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order:

```
ST-003  ← data correctness bug (highest risk — do first)
ST-001  ← security gap
ST-002  ← security gap / decision required
ST-004  ← input validation
ST-005  ← wrong DRF pattern
ST-006  ← wrong Django pattern
ST-007  ← DRY
ST-008  ← consistency / decision required
ST-009  ← import hygiene
ST-010  ← dead code
ST-011  ← cleanup (depends on ST-005)
ST-012  ← cleanup (depends on ST-005, ST-011)
```

## Ticket-Specific Context

- Auth: SimpleJWT — access/refresh tokens stored as **HTTP-only cookies** set by Nuxt
  server routes (not Authorization headers)
- Port 9020 is Docker-internal only — not host-bound in production
- The hardening tasks (Phases 1–5) are complete — see `hardening-tasks/PROGRESS.md`
