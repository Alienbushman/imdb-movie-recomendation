# Progress — Ticket 005

Rows are ordered by execution order. Work top-to-bottom unless dependencies allow otherwise.

| ID | Title | Priority | Status | Dependencies | Notes |
|---|---|---|---|---|---|
| ST-001 | Create SQLite Scored Store | High | Done | — | `app/services/scored_store.py` created |
| ST-002 | Pipeline Integration (Write + Slim) | High | Done | ST-001 | `_state` no longer holds large collections |
| ST-003 | Route GET Endpoints to DB | High | Done | ST-002 | `filter_recommendations` removed |
| ST-004 | Deduplicate name_lookup + Cache Check | Low | Done | — | `name.basics` loaded once; 16 KB cache check |

## Completion

4 / 4 complete
