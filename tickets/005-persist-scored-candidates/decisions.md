# TICKET-005 Decisions Log

Record non-obvious implementation choices here as subtasks are completed.

## Format

```
### [Subtask N — Title] Short description of the decision
**Context:** What was unclear or had multiple valid options.
**Decision:** What was chosen.
**Reason:** Why this option over the alternatives.
```

## Decisions

### [Subtask 01] Store `is_anime` as a column using `getattr` fallback
**Context:** `CandidateTitle.is_anime` doesn't exist until TICKET-004 is implemented. Needed to store the column in SQLite now without breaking the current codebase.
**Decision:** `getattr(c, "is_anime", "Animation" in c.genres)` — returns `c.is_anime` when present (post-004), otherwise falls back to the genre heuristic.
**Reason:** Zero-change forward compatibility. When 004 lands, the DB write automatically uses the proper whitelist-based value without any code change in `scored_store.py`.

### [Subtask 02] Keep `_state["titles"]` (rated titles) in memory
**Context:** "Nothing needs to be fully cached" — but generating `similar_to` and director-match explanations on GET requests requires the rated titles list.
**Decision:** Keep `_state["titles"]` (typically 500–2000 `RatedTitle` objects, ~2 MB). This is the minimum required for explanation quality.
**Reason:** Without rated titles, `similar_to` and director-match explanations return empty — a significant quality regression. 2 MB is negligible against the GB savings from removing `candidates` and `scored`.

### [Subtask 03] `POST /recommendations/filter` returns 409 without a pipeline run
**Context:** Previously returned 409 via a `ValueError` caught from `filter_recommendations`. After removing that function the guard needed to be explicit.
**Decision:** Check `has_scored_results()` directly and raise HTTPException 409 before calling `get_recommendations_from_db`.
**Reason:** Cleaner control flow — no exception used for normal flow control.
