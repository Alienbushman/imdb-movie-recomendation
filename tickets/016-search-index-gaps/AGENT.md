# Agent Instructions — Ticket 016

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for execution.

---

## Goal

Two surgical fixes to make search and browse features work correctly regardless of
which titles the user has already rated and whether the server has restarted.

No new features, no schema migrations of existing data. ST-002 adds a new table;
delete `data/cache/scored_candidates.db` to force a rebuild only if the schema
`CREATE TABLE IF NOT EXISTS` path fails — it normally just adds the table on first
pipeline run.

---

## Subtask Order

```
ST-001  ← people index from rated titles (no deps — modifies pipeline.py only)
ST-002  ← persist rated titles for search (no deps — modifies scored_store.py + pipeline.py + routes.py)
```

Both have no dependencies and can run in either order.

---

## Ticket-Specific Context

### Why directors are available without changing candidates.py

`RatedTitle.directors: list[str]` is always populated from the IMDB ratings CSV.
`titles` (the list of `RatedTitle`) is in scope in `pipeline.py` throughout the
people-writing block. No candidates.py changes needed for ST-001.

### title_people rows for rated titles

Adding `(imdb_id, name_id, role)` rows for rated title IDs means those IDs appear
in `title_people` but NOT in `scored_candidates`. The JOIN in `query_titles_by_person`
will silently ignore them — people will appear in search with a representative
`title_count`, but only their unrated films show in the browse results. That's the
correct behaviour for now.

### Interaction with ticket 015 ST-001

Ticket 015 ST-001 adds `rated_writers` to the `candidates.py` return signature.
Ticket 016 ST-001 does NOT touch `candidates.py` at all, so there is no conflict.

### rated_titles table and DB migration

`_ensure_schema` uses `CREATE TABLE IF NOT EXISTS`, so the new `rated_titles` table
is created automatically on the next pipeline run. No manual DB migration needed.
The table is cleared and repopulated on every pipeline run (DELETE + INSERT), so
it always reflects the current watchlist.
