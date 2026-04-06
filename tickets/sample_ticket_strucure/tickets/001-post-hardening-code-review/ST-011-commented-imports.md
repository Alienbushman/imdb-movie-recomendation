# ST-011 — Remove commented-out imports

**Priority:** Low  
**File:** `platform-backend/orchestrator/authenticator/views.py:12-13`  
**Depends on:** ST-005 (do ST-005 first — it removes the active `permission_classes` import from the same file)

## Problem

Two imports are commented out and are duplicates of active imports on adjacent lines:

```python
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
# from rest_framework.decorators import permission_classes    ← delete
# from rest_framework.permissions import IsAuthenticated      ← delete
```

## Fix

Read `authenticator/views.py` before editing to confirm the exact current line numbers
(ST-005 will have changed this file, so the line numbers from the original may be stale).

Delete the two commented-out import lines. No other changes.

Note: after ST-005 is complete, `from rest_framework.decorators import permission_classes`
will also be gone (ST-005 removes it). Do not re-remove it here — just remove the
commented-out lines.

## Files Changed

```
platform-backend/orchestrator/authenticator/views.py
```

## Commit Message

```
fix: remove commented-out duplicate imports in authenticator/views.py
```

## Tests

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test authenticator.tests authenticator.tests_security

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```
