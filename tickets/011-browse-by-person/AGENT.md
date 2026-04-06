# Agent Instructions — Ticket 011

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for implementation.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order:

```
ST-001  ← backend person search + DB schema extension (no deps)
ST-002  ← backend titles-by-person endpoint (depends on ST-001)
ST-003  ← frontend person page + routing (depends on ST-001, parallel with ST-002)
ST-004  ← frontend results + role filter (depends on ST-002, ST-003)
```

ST-002 and ST-003 can be worked in parallel once ST-001 is done.

---

## Ticket-Specific Context

- **Read `scored_store.py` and `pipeline.py` in full before writing any code** — ST-001
  extends the DB schema and the write step; touching these files without reading them first
  will produce incorrect or duplicate logic
- **Read `candidates.py`** to understand how `name_lookup` is built and what fields
  `CandidateTitle` carries for crew (directors, cast, etc.) — the exact field names matter
  for the SQL population step
- The `people` and `title_people` tables are populated during the same pipeline write that
  writes scored candidates — not lazily on first request
- The `/similar` page (ticket 009) is a close structural parallel: same autocomplete
  pattern, same FilterDrawer reuse, same RecommendationCard grid — read `similar.vue` and
  the `similar` store before building the `person` equivalents
- Frontend uses Nuxt 4 + Vuetify 4; `v-autocomplete` is already used on the similar page —
  reuse that pattern
- The `FilterDrawer` component is already extracted and accepts a page-context prop; check
  how the similar page passes context before replicating it
- Lint: `uv run ruff check app/` (backend), `cd frontend && npx nuxt typecheck` (frontend)
- Tests: `uv run pytest tests/ -q`
