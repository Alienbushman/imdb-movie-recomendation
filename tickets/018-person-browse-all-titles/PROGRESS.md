# Progress — Ticket 018

Rows are ordered by execution order. Work top-to-bottom unless dependencies allow otherwise.

| ID | Title | Priority | Status | Dependencies | Notes |
|---|---|---|---|---|---|
| ST-001 | Index actor/writer/composer crew from rated titles in title_people | High | Done | — | |
| ST-002 | Enrich rated_titles table and UNION into query_titles_by_person | High | Done | ST-001 | Rated titles must be indexed before the UNION can return them |
| ST-003 | Frontend: seen/unseen toggle + seen badge on person browse | Medium | Done | ST-002 | Needs is_rated field in API response |

## Completion

3 / 3 complete
