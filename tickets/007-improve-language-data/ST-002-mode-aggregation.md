---
id: ST-002
ticket: "007"
title: "Use Mode Instead of First for Language Resolution"
priority: High
risk: medium
status: Done
dependencies: ["ST-001"]
subsystems: [backend]
---

# ST-002 — Use Mode Instead of First for Language Resolution

**Priority:** High
**Risk:** Medium
**Files:** `app/services/candidates.py`

## Problem

The current language resolution logic sorts rows by `(titleId, _is_orig DESC)` and takes
`first()`. When a title has multiple `isOriginalTitle=1` rows with different languages, the
result is determined by an undefined secondary sort — non-deterministic across dataset rebuilds.

## Pre-conditions

```bash
# Confirm ST-001 (ambiguous regions) is already applied
grep -n "_AMBIGUOUS_REGIONS" app/services/candidates.py
# Expected: at least 2 matches

# Confirm the first() pattern still exists
grep -n "first()" app/services/candidates.py
# Expected: at least 1 match in _load_language_data

# Confirm akas_sorted or equivalent exists
grep -n "akas_sorted\|sort_values" app/services/candidates.py
# Expected: at least 1 match
```

## Fix

Read `app/services/candidates.py` before editing to confirm the current state.

### Step 1 — Replace `first()` with mode aggregation

Replace the current `akas_sorted / groupby / first()` block in `_load_language_data()` with:

```python
# Primary: most common resolved language among isOriginalTitle=1 rows
lang_by_title: dict[str, str] = (
    akas[akas["_is_orig"] == 1]
    .dropna(subset=["_resolved"])
    .groupby("titleId")["_resolved"]
    .agg(lambda s: s.mode().iloc[0])
    .to_dict()
)

# Fallback: for titles with no original-title match, use mode across all rows
no_orig = title_ids - lang_by_title.keys()
if no_orig:
    fallback = (
        akas[akas["titleId"].isin(no_orig)]
        .dropna(subset=["_resolved"])
        .groupby("titleId")["_resolved"]
        .agg(lambda s: s.mode().iloc[0])
        .to_dict()
    )
    lang_by_title.update(fallback)
```

### Step 2 — Remove now-unused `akas_sorted` variable

Remove the `akas_sorted` assignment and the `sort_values` call that produced it. The
`_is_orig` column is still needed for the `akas["_is_orig"] == 1` filter above.

## Anti-patterns

- Do NOT remove the `_is_orig` column — it is still used for filtering original-title rows
- Do NOT change the `_resolved` column derivation — that was done in ST-001
- Do NOT use `apply` on the full DataFrame — `groupby` + `agg` is much faster

## Post-conditions

```bash
# Confirm first() is gone from _load_language_data
grep -n "first()" app/services/candidates.py
# Expected: 0 matches in the _load_language_data function

# Confirm mode() is used
grep -n "mode()" app/services/candidates.py
# Expected: at least 1 match

# Confirm akas_sorted is gone
grep -n "akas_sorted" app/services/candidates.py
# Expected: 0 matches
```

## Tests

```bash
# Backend lint
uv run ruff check app/

# Backend tests
uv run pytest tests/ -q
```

## Files Changed

```
app/services/candidates.py
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
fix: use mode aggregation for deterministic language resolution
```
