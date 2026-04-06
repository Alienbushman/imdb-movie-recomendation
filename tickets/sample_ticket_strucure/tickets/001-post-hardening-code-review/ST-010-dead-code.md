# ST-010 — Remove StockDateValueFromScratchView dead code

**Priority:** Low  
**File:** `platform-backend/orchestrator/pull_data/views.py:171-223`

## Problem

`StockDateValueFromScratchView` is a legacy view that manually loops over downloaded stock
values and saves them one-by-one via serializer. The current production path is
`StockDateValueView` which delegates to `fetch_and_process_stock_data()`. The legacy view
appears to be unregistered and is confusing when reading the file.

## Fix

Before deleting anything, verify the view is truly dead:

```bash
# Confirm it has no URL registration
grep -r "StockDateValueFromScratchView" platform-backend/orchestrator/
```

If the grep returns only the class definition itself (no imports or URL references), proceed:

1. Read `pull_data/views.py` to confirm the exact line range of the class and its decorator.
2. Delete the `@swagger_auto_schema` decorator and the entire `StockDateValueFromScratchView`
   class.

If the grep finds references elsewhere, stop and report — do not delete.

## Post-conditions

```bash
# Verify the dead class is gone
grep -rn "StockDateValueFromScratchView" platform-backend/orchestrator/  # expect 0 hits
```

## Files Changed

```
platform-backend/orchestrator/pull_data/views.py
```

## Commit Message

```
fix: remove StockDateValueFromScratchView dead code
```

## Tests

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test pull_data.tests

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```
