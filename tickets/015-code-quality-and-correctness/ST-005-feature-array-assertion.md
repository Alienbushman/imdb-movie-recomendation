---
id: ST-005
ticket: "015"
title: "Assert feature completeness in feature_vector_to_array"
priority: Low
risk: zero
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 05 — Assert feature completeness in feature_vector_to_array

---

## Objective

`feature_vector_to_array()` uses `row.get(name, 0)` for each name in
`feature_names`. If a feature is added to `features_to_dataframe` but accidentally
omitted from `feature_vector_to_array`'s `row` dict, it silently defaults to `0.0`
at inference time — wrong predictions with no error signal.

Add an assertion that fires immediately if any model feature name has no matching
key in `row`.

---

## Pre-conditions

Confirm current state — no assertion exists:

```bash
grep -n "assert" app/services/features.py | grep -i "feature"
```

Expected: zero matches.

---

## Fix

### Step 1 — `app/services/features.py`

Find the end of `feature_vector_to_array()`, just before the `return` statement:

```python
    row.update(fv.genre_affinity)
    row.update(fv.genre_flags)
    row.update(fv.language_flags)
    row.update(fv.type_flags)
    row.update(fv.genre_pair_flags)
    return np.array([row.get(name, 0) for name in feature_names], dtype=float)
```

Replace with:

```python
    row.update(fv.genre_affinity)
    row.update(fv.genre_flags)
    row.update(fv.language_flags)
    row.update(fv.type_flags)
    row.update(fv.genre_pair_flags)
    missing = [name for name in feature_names if name not in row]
    assert not missing, f"feature_vector_to_array missing keys: {missing}"
    return np.array([row[name] for name in feature_names], dtype=float)
```

Note: the final line also switches from `row.get(name, 0)` to `row[name]` — the
assertion above guarantees all keys are present, so the `.get` fallback is no
longer needed. This makes any future omission raise a `KeyError` instead of
silently using `0`.

---

## Post-conditions

Confirm the assertion line is present:

```bash
grep -n "assert not missing" app/services/features.py
```

Expected: one match.

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

All existing tests must pass — no feature names are currently missing from `row`,
so the assertion should never fire in normal operation.

---

## Files Changed

- `app/services/features.py`

---

## Commit Message

```
fix: assert all feature names are present in feature_vector_to_array (ST-005)
```
