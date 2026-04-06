# Agent Instructions — Ticket 008

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

---

## Subtask Order

All subtasks are independent — can run in parallel:

```
ST-001  ← client-side sort controls
ST-002  ← scroll-to-top FAB
ST-003  ← grid density toggle + result count
```

## Ticket-Specific Context

- All changes are pure frontend — no backend or schema changes
- ST-001 and ST-003 both modify the "sort bar" area in `index.vue` — if done sequentially,
  do ST-001 first (ST-003 extends the sort bar ST-001 creates)
- Sort state uses `@pinia-plugin-persistedstate/nuxt` — if ticket 006 ST-001 is not yet
  done, that plugin must be installed as part of ST-001 here
- `@vueuse/core` may need to be added as a dependency for `useLocalStorage` in ST-003
  (check if already installed first)
- Type-check with `cd frontend && npx nuxt typecheck`
