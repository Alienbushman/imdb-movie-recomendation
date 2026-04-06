# ST-004 — Add input validation for StockDateValueView

**Priority:** High  
**File:** `platform-backend/orchestrator/pull_data/views.py:149-168`

## Problem

`StockDateValueView.post()` accepts `num_companies`, `start_date`, and `end_date` from the
request body but does not validate their types or ranges before passing them to
`fetch_and_process_stock_data()`. A malformed request (e.g., `num_companies=-1` or
`start_date="not-a-date"`) will either crash downstream or produce silent bad data.

Additionally, the `_missing_fields` check on line 150 lists `end_date` as required, but the
Swagger schema marks it optional — a separate inconsistency covered by ST-008, but worth
fixing here too since they are in the same method.

## Fix

Read `pull_data/views.py` before editing to confirm current line numbers.

Add validation immediately after the missing-fields check:

```python
try:
    num_companies = int(num_companies)
    if num_companies < 1 or num_companies > 5000:
        raise ValueError
except (ValueError, TypeError):
    return Response(
        {'error': 'num_companies must be a positive integer (max 5000)'},
        status=status.HTTP_400_BAD_REQUEST,
    )

try:
    datetime.date.fromisoformat(start_date)
    if end_date:
        datetime.date.fromisoformat(end_date)
except ValueError:
    return Response(
        {'error': 'start_date and end_date must be in YYYY-MM-DD format'},
        status=status.HTTP_400_BAD_REQUEST,
    )
```

Note: `datetime` is already imported at the top of `pull_data/views.py`.

## Files Changed

```
platform-backend/orchestrator/pull_data/views.py
platform-backend/orchestrator/pull_data/tests.py
```

## Commit Message

```
fix: add input validation to StockDateValueView
```

## Tests

Add cases to `pull_data/tests.py`:
- `num_companies = -1` → 400
- `num_companies = "abc"` → 400
- `start_date = "not-a-date"` → 400
- Valid payload → passes validation (mock `fetch_and_process_stock_data`)

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test pull_data.tests

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```
