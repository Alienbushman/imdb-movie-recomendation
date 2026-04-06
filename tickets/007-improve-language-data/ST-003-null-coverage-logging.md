---
id: ST-003
ticket: "007"
title: "Log Language Null Coverage in Pipeline"
priority: Low
risk: zero
status: Done
dependencies: []
subsystems: [backend]
---

# ST-003 — Log Language Null Coverage in Pipeline

**Priority:** Low
**Risk:** Zero
**Files:** `app/services/candidates.py`

## Problem

No metrics are logged for how many candidate titles end up with `language=None`. Filtering by
language silently excludes these titles, so users may get fewer results than expected without
any indication of why.

## Pre-conditions

```bash
# Confirm _load_language_data function exists
grep -n "def _load_language_data" app/services/candidates.py
# Expected: 1 match

# Confirm logger is available
grep -n "logger" app/services/candidates.py
# Expected: at least 1 match
```

## Fix

Read `app/services/candidates.py` before editing to confirm the current state.

At the end of `_load_language_data()`, after the existing `logger.info(...)` call that reports
resolved counts, add:

```python
null_count = len(title_ids) - len(lang_by_title)
logger.info(
    "  Language null rate: %d / %d titles (%.1f%%) have no language resolved",
    null_count,
    len(title_ids),
    100 * null_count / max(len(title_ids), 1),
)
```

## Post-conditions

```bash
# Confirm the log line exists
grep -n "Language null rate" app/services/candidates.py
# Expected: 1 match
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
feat: log language null coverage rate in pipeline
```
