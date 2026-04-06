# Agent Instructions — Ticket 009

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for implementation.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order:

```
ST-001  ← backend title search (no deps)
ST-002  ← backend similarity engine (depends on ST-001)
ST-003  ← frontend similar page + routing (depends on ST-001, parallel with ST-002)
ST-004  ← frontend results + seen/unseen filter (depends on ST-002, ST-003)
```

ST-002 and ST-003 can be worked in parallel once ST-001 is done.

## Ticket-Specific Context

- Backend uses FastAPI with synchronous endpoints and httpx for HTTP (sync, not async)
- Similarity is content-based (genre Jaccard + crew overlap), NOT ML model embedding
- The scored candidates SQLite DB (`data/cache/scored_candidates.db`) is the primary data source
- User's rated titles are in `_state.rated_titles` (populated after pipeline run)
- Frontend uses Nuxt 4 + Vuetify 4 with `v-autocomplete` for the search bar
- The `FilterDrawer` component is already extracted — reuse it on the similar page
- `RecommendationCard` needs to handle both `Recommendation` and `SimilarTitle` props
- Lint: `uv run ruff check app/` (backend), `cd frontend && npx nuxt typecheck` (frontend)
- Tests: `uv run pytest tests/ -q`
