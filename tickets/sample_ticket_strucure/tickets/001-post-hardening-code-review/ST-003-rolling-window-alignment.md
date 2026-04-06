# ST-003 — Fix rolling-window symbol alignment bug in GetModelPredictionsView

**Priority:** High
**Locate:** `grep -n "output_df\[prediction_column_name\] = predictions" platform-backend/orchestrator/daily_prediction/views.py`

## Problem

The loop that builds the 5-day rolling average assigns historical predictions by *position*,
not by *symbol*. If the set of stocks present in the data differs between any two days
(e.g., a newly listed stock, a delisted stock, or a stock with missing data for one day),
the predictions from historical days are silently assigned to the wrong rows.

```python
# Current — positional assignment, WRONG when stock sets differ between days
for index in range(1, min(5, len(unique_days))):
    predictions = list(daily_df[daily_df['date'] == unique_days[index]]['prediction'])
    prediction_column_name = f'prediction-{index}-days-ago'
    historic_prediction_columns.append(prediction_column_name)
    output_df[prediction_column_name] = predictions   # <-- assumes same order & length
```

## Pre-conditions

```bash
# Confirm the positional assignment pattern still exists
grep -n "output_df\[prediction_column_name\] = predictions" \
  platform-backend/orchestrator/daily_prediction/views.py
# Expected: exactly 1 match

# Confirm tests are green before we start
cd platform-backend/orchestrator && python manage.py test --verbosity=0
```

## Fix

Read `daily_prediction/views.py` before editing to confirm the current state.

Replace the positional assignment loop with a symbol-keyed merge:

```python
for index in range(1, min(5, len(unique_days))):
    hist = daily_df[daily_df['date'] == unique_days[index]][['symbol', 'prediction']]
    prediction_column_name = f'prediction-{index}-days-ago'
    historic_prediction_columns.append(prediction_column_name)
    output_df = output_df.merge(
        hist.rename(columns={'prediction': prediction_column_name}),
        on='symbol',
        how='left',
    )
```

Stocks missing from a historical day will get `NaN` for that column. The existing
`.mean(axis=1)` call on `output_df[historic_prediction_columns]` already skips NaN
by default (`skipna=True`), so partial history is handled gracefully.

## Anti-patterns

- Do NOT use positional indexing (`.iloc`) — that is the same bug with extra steps
- Do NOT iterate row-by-row with a Python loop — use `merge`/`join` for vectorized alignment
- Do NOT fill NaN with 0 — a missing day should be excluded from the mean, not counted as 0%

## Post-conditions

```bash
# Confirm the positional assignment is gone
grep -n "output_df\[prediction_column_name\] = predictions" \
  platform-backend/orchestrator/daily_prediction/views.py
# Expected: 0 matches

# Confirm the merge pattern is present
grep -n "output_df.merge" \
  platform-backend/orchestrator/daily_prediction/views.py
# Expected: at least 1 match
```

## Tests

Add a test in `daily_prediction/tests.py` that:
1. Builds a minimal DataFrame where day 0 has stocks `[A, B, C]` and day 1 has stocks `[A, C]`
   (B is missing from history).
2. Runs the rolling-average logic (either by calling the view directly or by extracting the
   logic into a helper you can unit-test).
3. Asserts that stock B's historical column is `NaN` (not a prediction belonging to C).

Expected assertions:
- `output_df.loc[output_df['symbol'] == 'A', 'prediction-1-days-ago']` == value from day 1
- `output_df.loc[output_df['symbol'] == 'B', 'prediction-1-days-ago']` is `NaN`
- `output_df.loc[output_df['symbol'] == 'C', 'prediction-1-days-ago']` == value from day 1

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test daily_prediction.tests

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```

## Files Changed

```
platform-backend/orchestrator/daily_prediction/views.py
platform-backend/orchestrator/daily_prediction/tests.py
```

## Rollback

```bash
git revert HEAD  # single logical change, clean revert
```

## Commit Message

```
fix: fix rolling-window symbol alignment bug in GetModelPredictionsView
```
