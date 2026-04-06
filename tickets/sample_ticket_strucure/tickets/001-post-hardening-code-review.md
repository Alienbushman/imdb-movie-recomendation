# 001 — Post-Hardening Code Review: Quality, Security Gaps & Bugs

## Summary

Code review conducted after the Phase 1 hardening work. Covers three categories of concern:
security gaps that survived hardening, code quality issues (dead code, wrong patterns,
duplicate logic), and a logic bug in the prediction rolling window.

## Priority

| Priority | Count |
|---|---|
| High (security / data correctness) | 4 |
| Medium (wrong patterns / DRY) | 5 |
| Low (cleanup) | 3 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](001-post-hardening-code-review/ST-001-csrf-middleware.md) | Re-enable CSRF middleware or document the waiver | High | Open |
| [ST-002](001-post-hardening-code-review/ST-002-unauthenticated-predictions.md) | Document or restrict AllowAny on GetModelPredictionsView | High | Open |
| [ST-003](001-post-hardening-code-review/ST-003-rolling-window-alignment.md) | Fix rolling-window symbol alignment bug in GetModelPredictionsView | High | Open |
| [ST-004](001-post-hardening-code-review/ST-004-input-validation.md) | Add input validation for num_companies, start_date, end_date | High | Open |
| [ST-005](001-post-hardening-code-review/ST-005-permission-classes-cbv.md) | Replace @permission_classes decorator with class attribute on CBVs | Medium | Open |
| [ST-006](001-post-hardening-code-review/ST-006-settings-import.md) | Fix `from orchestrator import settings` → `from django.conf import settings` | Medium | Open |
| [ST-007](001-post-hardening-code-review/ST-007-dry-model-registry.md) | Extract duplicated ModelRegistry update logic into a shared helper | Medium | Open |
| [ST-008](001-post-hardening-code-review/ST-008-end-date-consistency.md) | Reconcile end_date required/optional inconsistency across views and Swagger | Medium | Open |
| [ST-009](001-post-hardening-code-review/ST-009-datetime-import.md) | Move inline `import datetime` to module top level | Medium | Open |
| [ST-010](001-post-hardening-code-review/ST-010-dead-code.md) | Remove StockDateValueFromScratchView dead code | Low | Open |
| [ST-011](001-post-hardening-code-review/ST-011-commented-imports.md) | Remove commented-out imports | Low | Open |
| [ST-012](001-post-hardening-code-review/ST-012-unused-imports.md) | Remove unused imports (render, get_object_or_404) | Low | Open |

## Files Reviewed

- `platform-backend/orchestrator/daily_prediction/views.py`
- `platform-backend/orchestrator/authenticator/views.py`
- `platform-backend/orchestrator/pull_data/views.py`
- `platform-backend/orchestrator/pull_data/management/commands/train_model.py`
- `platform-backend/orchestrator/orchestrator/middleware.py`
- `platform-frontend/server/api/pull-data/pull-latest-data.ts`

## Scope Fence

- Only modify files listed in each subtask's "Files Changed" section
- Do not refactor surrounding code, even if it looks wrong
- Do not update dependencies or configuration beyond what the subtask requires

## Open Questions

| ID | Question | Status | Resolution | Affects |
|---|---|---|---|---|
| Q-001 | Is ST-001 relevant? CSRF is handled by Nuxt proxy — port 9020 is Docker-internal only | Resolved | Option B — document the waiver, do not re-enable middleware | ST-001 |
| Q-002 | ST-002: restrict or document AllowAny on predictions endpoint? | Resolved | Document — it is a public cached endpoint, anyone should access it | ST-002 |
