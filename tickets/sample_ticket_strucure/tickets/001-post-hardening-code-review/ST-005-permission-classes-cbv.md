# ST-005 — Replace @permission_classes decorator with class attribute on CBVs

**Priority:** Medium  
**File:** `platform-backend/orchestrator/authenticator/views.py`

## Problem

All auth view classes use `@permission_classes([IsAuthenticated])` as a class decorator.
This is a pattern for function-based views. On class-based views the correct DRF pattern is a
class attribute:

```python
class GetAllUsersView(APIView):
    permission_classes = [IsAuthenticated]
```

The decorator form works because DRF's `APIView.as_view()` introspects it, but it is
non-standard, easy to misread, and will silently do the wrong thing if the class is ever
subclassed (the decorator does not inherit).

## Fix

Read `authenticator/views.py` before editing to confirm current class definitions.

For each of the six classes in `authenticator/views.py`:
- `GetAllUsersView`
- `CreateUserView`
- `CreateUsersView`
- `ResetPasswordView`
- `GetUsernameView`
- `DeleteUserView`

Remove the `@permission_classes([IsAuthenticated])` decorator and add
`permission_classes = [IsAuthenticated]` as a class attribute on the line after the `class`
declaration.

Also remove the now-unused import:
```python
from rest_framework.decorators import permission_classes
```

## Files Changed

```
platform-backend/orchestrator/authenticator/views.py
```

## Commit Message

```
fix: replace @permission_classes decorator with class attribute on auth CBVs
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

The `AuthByDefaultTest` suite in `tests_security.py` already covers that unauthenticated
requests return 401 — it should continue to pass without changes.
