# ST-008 — Reconcile end_date required/optional inconsistency

**Priority:** Medium  
**File:** `platform-backend/orchestrator/pull_data/views.py:150-152`

## Problem

`StockDateValueView.post()` validates `end_date` as a required field in the missing-fields
check, but the Swagger schema for the same endpoint marks `end_date` as optional. Callers
following the API docs will receive a 400 error for an omitted field the docs say is optional.

## Decision

First, read the frontend store to find out what the frontend actually sends:

```bash
# Check what the frontend passes
cat platform-frontend/stores/dailyPredictionStore.ts
# or
grep -r "end_date\|endDate" platform-frontend/stores/ platform-frontend/server/api/pull-data/
```

Then choose:

**Option B — end_date is optional (likely correct):**

If the frontend omits `end_date` or passes it conditionally, remove it from the
`_missing_fields` check. Handle a missing value downstream by defaulting to today's date:

```python
end_date = data.get('end_date') or str(datetime.date.today())
```

**Option A — end_date is required:**

If the frontend always sends `end_date`, add it to the `required` list in the
`@swagger_auto_schema` request body schema so the docs match the validation.

## Files Changed

```
platform-backend/orchestrator/pull_data/views.py
```

## Commit Message

```
fix: make end_date optional in StockDateValueView to match API docs
```

(If Option A: `fix: mark end_date as required in StockDateValueView swagger schema`)

## Tests

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test pull_data.tests

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```
