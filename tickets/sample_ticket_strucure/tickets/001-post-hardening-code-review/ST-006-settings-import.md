# ST-006 — Fix `from orchestrator import settings` → `from django.conf import settings`

**Priority:** Medium  
**File:** `platform-backend/orchestrator/pull_data/views.py:13`

## Problem

```python
from orchestrator import settings   # wrong
```

This imports the settings module directly from the `orchestrator` package, bypassing Django's
settings override mechanism. `override_settings()` in tests will not work for this module,
meaning any test that overrides settings will silently see the wrong values.

## Fix

Read `pull_data/views.py` before editing to confirm the current import line.

Replace the import:

```python
# Before
from orchestrator import settings

# After
from django.conf import settings
```

Also check whether any other file in `pull_data/` uses the same wrong import pattern and fix
those too:

```bash
grep -r "from orchestrator import settings" platform-backend/orchestrator/pull_data/
```

## Post-conditions

```bash
# Verify no wrong-pattern imports remain
grep -rn "from orchestrator import settings" platform-backend/orchestrator/pull_data/  # expect 0 hits
```

## Files Changed

```
platform-backend/orchestrator/pull_data/views.py
# plus any other pull_data files found by the grep above
```

## Commit Message

```
fix: use django.conf.settings instead of direct orchestrator import in pull_data
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
