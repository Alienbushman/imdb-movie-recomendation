# ST-002 — Document AllowAny on GetModelPredictionsView

**Priority:** High
**File:** `platform-backend/orchestrator/daily_prediction/views.py:58`

## Problem

`GetModelPredictionsView` has `permission_classes = [AllowAny]`. This is undocumented and
inconsistent with the auth-by-default policy enforced elsewhere (Task 1.3).

## Decision

**Option A — Intended public (chosen):**

This is a cached prediction endpoint that serves read-only, non-sensitive rating data.
Anyone should be able to access it. Keep `AllowAny` but document the intent.

## Fix

Read `daily_prediction/views.py` before editing to confirm the current class definition.

Add a comment above the `permission_classes` line:

```python
class GetModelPredictionsView(APIView):
    # Public endpoint: prediction ratings are read-only cached data.
    # AllowAny is intentional — re-evaluate before adding write operations.
    permission_classes = [AllowAny]
```

Also update the Swagger `operation_description` to note that no auth is required.

## Post-conditions

```bash
# Verify AllowAny is still present with a comment
grep -A2 "AllowAny" platform-backend/orchestrator/daily_prediction/views.py  # expect AllowAny + comment
```

## Files Changed

```
platform-backend/orchestrator/daily_prediction/views.py
```

## Commit Message

```
docs: document AllowAny intent on GetModelPredictionsView
```

## Tests

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test daily_prediction.tests

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```
