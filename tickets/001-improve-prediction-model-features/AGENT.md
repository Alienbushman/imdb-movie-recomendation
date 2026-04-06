# Agent Instructions — Ticket 001

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Done** — All subtasks complete. No agent action needed.

---

## Subtask Order

Work through subtasks in PROGRESS.md row order:

```
ST-001  ← genre affinity scores (no deps)
ST-002  ← director/actor taste features (no deps)
ST-003  ← language as feature (no deps)
ST-004  ← writer taste features (no deps)
ST-005  ← title type as feature (no deps)
ST-006  ← genre interaction pairs (depends on ST-001)
ST-007  ← popularity tier + title age (no deps)
ST-008  ← composers + cinematographers (no deps)
ST-009  ← TMDB API integration (no deps)
ST-010  ← OMDb API integration (no deps)
```

## Ticket-Specific Context

- All subtasks modify `app/services/features.py` and/or `app/services/model.py`
- Feature ordering in `feature_vector_to_array()` must match `features_to_dataframe()`
- After any feature change, `data/taste_model.pkl` must be deleted and model retrained
- The 5 `N806` lint warnings in `model.py` (uppercase `X`) are intentional ML convention
- TMDB and OMDb integrations are opt-in via env vars — features default to `0.0` when keys absent
