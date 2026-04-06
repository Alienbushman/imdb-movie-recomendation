---
id: ST-NNN
ticket: NNN
title: "Short descriptive title"
priority: High         # Critical | High | Medium | Low
risk: medium           # zero | low | medium | high
status: Open           # Open | In Progress | Blocked | Done | Won't Do
dependencies: []       # e.g. ["ST-001", "ST-002"]
subsystems: []         # e.g. [backend-auth, django-settings, frontend-store]
---

# ST-NNN — Short Descriptive Title

**Priority:** High
**Risk:** Medium
**Files:** `platform-backend/orchestrator/path/to/file.py`

## Problem

What is wrong and why it matters. Be specific — include code snippets of the current
broken/wrong state if applicable.

## Pre-conditions

<!-- Executable checks that must pass before starting. Delete section if none. -->

```bash
# Example: verify dependency ST-001 actually landed
grep -c "expected_pattern" platform-backend/orchestrator/path/to/file.py  # expect >= 1
```

## Fix

Step-by-step instructions. Include BEFORE/AFTER code blocks where applicable.

1. Read `path/to/file.py` — confirm current state matches the Problem section
2. Replace X with Y
3. ...

## Tests

<!-- Targeted test command, then full suite. -->

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test <app>.tests

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```

<!-- If new test cases should be added, describe them here. -->

## Post-conditions

<!-- Executable checks that must pass after completing the fix. Delete section if none. -->

```bash
# Example: verify the bad pattern is gone
grep -c "bad_pattern" platform-backend/orchestrator/path/to/file.py  # expect 0
```

## Files Changed

```
platform-backend/orchestrator/path/to/file.py
```

## Commit Message

```
fix: short description of what was fixed
```

## Gotchas

<!-- (optional) Known pitfalls an agent might hit. Delete section if none. -->
