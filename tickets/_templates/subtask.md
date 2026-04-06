---
id: ST-NNN
ticket: "NNN"
title: "Short descriptive title"
priority: High         # High | Medium | Low
risk: medium           # zero | low | medium | high
status: Open           # Open | In Progress | Blocked | Done | Won't Do
dependencies: []       # e.g. ["ST-001", "ST-002"]
subsystems: []         # e.g. [backend, frontend, pipeline]
---

# ST-NNN — Short Descriptive Title

**Priority:** High
**Risk:** Medium
**Files:** `app/services/example.py`

## Problem

What is wrong and why it matters. Be specific — include code snippets of the current
broken/wrong state if applicable.

## Pre-conditions

<!-- Executable checks that must pass before starting. Delete section if none. -->

```bash
# Example: verify the pattern still exists
grep -n "anchor_pattern" app/services/example.py
# Expected: at least 1 match
```

## Fix

Step-by-step instructions. Include BEFORE/AFTER code blocks where applicable.

1. Read `app/services/example.py` — confirm current state matches the Problem section
2. Replace X with Y
3. ...

## Anti-patterns

<!-- What NOT to do. List 2-3 common mistakes an agent might make on this subtask.
     Omit this section for trivial cleanup subtasks. -->

- Do NOT ...
- Do NOT ...

## Post-conditions

<!-- Executable checks that must pass after completing the fix. Delete section if none. -->

```bash
# Example: verify the bad pattern is gone
grep -n "bad_pattern" app/services/example.py
# Expected: 0 matches
```

## Tests

```bash
# Backend lint
uv run ruff check app/

# Backend tests
uv run pytest tests/ -q

# Frontend types (if frontend files changed)
cd frontend && npx nuxt typecheck
```

## Files Changed

```
app/services/example.py
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
<type>: <imperative summary>
```

<!-- Use conventional commit types: fix, feat, refactor, docs, chore, test.
     The agent uses this exact string — keep it under 72 characters. -->

## Gotchas

<!-- (optional) Known pitfalls an agent might hit. Delete section if none. -->
