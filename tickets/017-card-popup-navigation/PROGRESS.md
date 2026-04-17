# Progress — Ticket 017

Rows are ordered by execution order. Work top-to-bottom unless dependencies allow otherwise.

| ID | Title | Priority | Status | Dependencies | Notes |
|---|---|---|---|---|---|
| ST-001 | Similar page deep-link support | Medium | Done | — | 2026-04-07 — store helper `selectSeedById` + page `onMounted` query-param handler |
| ST-002 | Person page deep-link support | Medium | Done | — | 2026-04-07 — store helper `selectPersonById` + page `onMounted` query-param handler |
| ST-003 | Find Similar button in card popup | Medium | Done | ST-001 | 2026-04-07 — button placed between View on IMDB and spacer, hidden when no imdb_id |
| ST-004 | Clickable director/actor chips in card popup | Medium | Done | ST-002 | 2026-04-07 — director + per-actor chips with `openPerson` handler; compact card face unchanged |

## Completion

4 / 4 complete
