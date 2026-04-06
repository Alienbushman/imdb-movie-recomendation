# Agent Instructions — Ticket 002

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Done** — All subtasks complete. No agent action needed.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order:

```
Phase 1 (parallel, no deps):  ST-001 + ST-002 + ST-005
Phase 2 (after ST-001 + ST-002): ST-003
Phase 3 (after ST-003):        ST-004
Phase 4 (parallel):            ST-006 (after ST-005) + ST-007 (after ST-004)
Phase 5 (after all):           ST-008
```

## Ticket-Specific Context

- `httpx` is used synchronously — use `httpx.Client`, not `AsyncClient`
- IMDB's `/ratings/export` endpoint may return 403 for private ratings lists
- Browser-like headers are required for the IMDB fetch (see `app/services/scrape.py`)
- Fetched CSV is cached to `data/watchlist.csv` so subsequent runs don't re-fetch
- The CSV upload endpoint (`POST /upload-watchlist`) is a fallback for when URL fetch fails
