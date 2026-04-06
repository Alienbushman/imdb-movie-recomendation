# ST-012 — Remove unused imports

**Priority:** Low  
**Files:**
- `platform-backend/orchestrator/authenticator/views.py`
- `platform-backend/orchestrator/pull_data/views.py`
- `platform-backend/orchestrator/daily_prediction/views.py`

**Depends on:** ST-005, ST-011 (do those first — both modify `authenticator/views.py`)

## Problem

| File | Import | Issue |
|---|---|---|
| `authenticator/views.py` | `from django.shortcuts import render, get_object_or_404` | `render` is unused; keep `get_object_or_404` |
| `pull_data/views.py` | `from django.shortcuts import render` | unused |
| `daily_prediction/views.py` | `from django.shortcuts import render` | unused |

## Fix

Read each file before editing to confirm the current import lines (earlier subtasks may have
shifted line numbers).

Remove only the unused names from each import line. Do not remove the entire import statement
if other names from the same module are still used.

After editing, run Ruff to catch any remaining unused imports:

```bash
cd platform-backend/orchestrator
ruff check . --select F401
```

Fix any additional F401 violations Ruff reports — but only remove imports, do not make other
changes.

## Files Changed

```
platform-backend/orchestrator/authenticator/views.py
platform-backend/orchestrator/pull_data/views.py
platform-backend/orchestrator/daily_prediction/views.py
```

## Commit Message

```
fix: remove unused render imports from view files
```

## Tests

```bash
# Full suite (no targeted subset — changes span three apps)
cd platform-backend/orchestrator
python manage.py test
cd ../../platform-frontend && npx vitest run
```
