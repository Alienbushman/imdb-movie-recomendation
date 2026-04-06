# ST-009 — Move inline `import datetime` to module top level

**Priority:** Medium  
**File:** `platform-backend/orchestrator/daily_prediction/views.py:111`

## Problem

`import datetime` appears inside the body of `GetModelPredictionsView.get()`, running on
every request that includes a `specific_date` query parameter. There is no circular import
here — `datetime` is a stdlib module. Inline imports inside method bodies are only justified
when avoiding a circular import.

## Fix

Read `daily_prediction/views.py` before editing to confirm the current top-of-file imports.

Move `import datetime` to the top of the file with the other stdlib imports. Remove the
inline import from inside the method body.

## Files Changed

```
platform-backend/orchestrator/daily_prediction/views.py
```

## Commit Message

```
fix: move inline datetime import to module top in daily_prediction/views.py
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
