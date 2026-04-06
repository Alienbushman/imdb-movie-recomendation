# Agent Instructions — Ticket 007

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

---

## Subtask Order

```
ST-003  ← logging (independent, safe — do first)
ST-001  ← block ambiguous regions (no deps)
ST-002  ← mode aggregation (depends on ST-001)
ST-004  ← add languages list field (depends on ST-001, ST-002)
```

ST-001 and ST-002 both edit `_load_language_data()` in `candidates.py` — do sequentially
to avoid merge conflicts.

## Ticket-Specific Context

- All changes are in `app/services/candidates.py` (+ schema files for ST-004)
- `_load_language_data()` is the core function being modified
- `_REGION_TO_LANG` maps country codes to languages — the region fallback is what's broken
  for multilingual countries (India, Belgium, Switzerland, Canada, etc.)
- ST-004 changes `CandidateTitle` schema — requires deleting both caches afterwards:
  - `data/cache/imdb_candidates.json`
  - `data/cache/scored_candidates.db`
- These cache deletions are on the Hard Stop List — confirm with user before deleting
