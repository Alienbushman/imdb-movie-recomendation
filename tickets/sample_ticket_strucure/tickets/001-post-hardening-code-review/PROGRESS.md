# Progress

Rows are ordered by suggested execution order. Work top-to-bottom.

| ID | Title | Priority | Status | Dependencies | Notes |
|---|---|---|---|---|---|
| ST-003 | Fix rolling-window symbol alignment bug | High | Open | — | |
| ST-001 | Re-enable CSRF middleware | High | Open | — | |
| ST-002 | Document AllowAny on GetModelPredictionsView | High | Open | — | Decision: keep AllowAny — public cached endpoint |
| ST-004 | Add input validation for StockDateValueView | High | Open | — | |
| ST-005 | Replace @permission_classes decorator on CBVs | Medium | Open | — | |
| ST-006 | Fix settings import in pull_data/views.py | Medium | Open | — | |
| ST-007 | Extract ModelRegistry update helper | Medium | Open | — | |
| ST-008 | Reconcile end_date required/optional | Medium | Open | — | ⚠️ Decision required — see subtask file |
| ST-009 | Move inline datetime import to module top | Medium | Open | — | |
| ST-010 | Remove StockDateValueFromScratchView dead code | Low | Open | — | |
| ST-011 | Remove commented-out imports | Low | Open | ST-005 | Do after ST-005 — same file, overlapping imports |
| ST-012 | Remove unused imports | Low | Open | ST-005, ST-011 | Do last — touches all three view files |

## Completion

0 / 12 complete
