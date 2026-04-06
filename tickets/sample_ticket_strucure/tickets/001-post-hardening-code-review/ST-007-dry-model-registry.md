# ST-007 — Extract duplicated ModelRegistry update logic into a shared helper

**Priority:** Medium  
**Files:**
- `platform-backend/orchestrator/daily_prediction/views.py:231-242`
- `platform-backend/orchestrator/pull_data/management/commands/train_model.py:79-89`

## Problem

The `ModelRegistry.objects.update_or_create(...)` block is duplicated verbatim in both
`TrainModelView.post()` and the `train_model` management command. Any future change to the
registry shape must be applied in two places.

## Fix

Read both files before editing to confirm the exact current content of each block.

Add a helper function in `daily_prediction/models.py`:

```python
def register_model(model_name: str, model_dir: str, activate: bool) -> None:
    """Register or update a model in ModelRegistry. Optionally set it as active."""
    if activate:
        ModelRegistry.objects.filter(is_active=True).update(is_active=False)
    ModelRegistry.objects.update_or_create(
        model_name=model_name,
        defaults={
            'version': model_name,
            'pkl_path': f"{model_dir}{model_name}.pkl",
            'format_csv_path': f"{model_dir}{model_name}_format.csv",
            'is_active': bool(activate),
        },
    )
```

Replace the duplicated blocks in both callers with a call to `register_model(...)`.

## Files Changed

```
platform-backend/orchestrator/daily_prediction/models.py
platform-backend/orchestrator/daily_prediction/views.py
platform-backend/orchestrator/pull_data/management/commands/train_model.py
```

## Commit Message

```
refactor: extract ModelRegistry update logic into register_model helper
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
