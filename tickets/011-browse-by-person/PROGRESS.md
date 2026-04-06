# Progress — Ticket 011

Rows are ordered by execution order. Work top-to-bottom unless dependencies allow otherwise.

| ID | Title | Priority | Status | Dependencies | Notes |
|---|---|---|---|---|---|
| ST-001 | Backend: Person Search + DB Schema Extension | High | Done | — | Name string used as name_id (nconst IDs not persisted in CandidateTitle) |
| ST-002 | Backend: Titles by Person Endpoint | High | Open | ST-001 | Query title_people join table |
| ST-003 | Frontend: Person Browse Page | Medium | Open | ST-001 | New page, nav link, autocomplete |
| ST-004 | Frontend: Results Display + Role Filter | Medium | Open | ST-002, ST-003 | Cards, role toggle, sort controls |

## Completion

1 / 4 complete
