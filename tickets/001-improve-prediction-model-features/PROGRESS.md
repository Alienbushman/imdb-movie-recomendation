# Progress — Ticket 001

Rows are ordered by execution order. Work top-to-bottom unless dependencies allow otherwise.

| ID | Title | Priority | Status | Dependencies | Notes |
|---|---|---|---|---|---|
| ST-001 | Genre Affinity Scores | High | Done | — | 23 `genre_X_affinity` features |
| ST-002 | Director/Actor Count + Mean | High | Done | — | 4 new features |
| ST-003 | Language as Feature | High | Done | — | 14 `lang_X` binary flags |
| ST-004 | Writer Taste Features | Medium | Done | — | `title.crew.tsv.gz` added to downloads |
| ST-005 | Title Type as Feature | Medium | Done | — | 4 `type_X` binary flags |
| ST-006 | Genre Interaction Pairs | Medium | Done | ST-001 | Auto-derived top-N genre pairs |
| ST-007 | Popularity Tier + Title Age | Medium | Done | — | 3 features: tier, age, log_votes |
| ST-008 | Composers + Cinematographers | Medium | Done | — | 4 taste features |
| ST-009 | TMDB API Integration | Medium | Done | — | 3 keyword features; opt-in via env var |
| ST-010 | OMDb API Integration | Medium | Done | — | 4 critic score features; opt-in via env var |

## Completion

10 / 10 complete
