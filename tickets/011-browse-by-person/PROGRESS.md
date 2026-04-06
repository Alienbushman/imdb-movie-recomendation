# Progress — Ticket 011

Rows are ordered by execution order. Work top-to-bottom unless dependencies allow otherwise.

| ID | Title | Priority | Status | Dependencies | Notes |
|---|---|---|---|---|---|
| ST-001 | Backend: Person Search + DB Schema Extension | High | Done | — | Name string used as name_id (nconst IDs not persisted in CandidateTitle) |
| ST-002 | Backend: Titles by Person Endpoint | High | Done | ST-001 | Two-query approach: COUNT then paginated SELECT |
| ST-003 | Frontend: Person Browse Page | Medium | Done | ST-001 | New page, nav link, autocomplete |
| ST-004 | Frontend: Results Display + Role Filter | Medium | Done | ST-002, ST-003 | Cards, role toggle, sort controls |

## Completion

4 / 4 complete
