# ST-NNN — Title (imperative verb phrase, e.g. "Fix X", "Add Y", "Remove Z")

**Priority:** High | Medium | Low
**Locate:** `grep -n "anchor pattern" path/to/file.py`

<!-- Use a grep anchor instead of hardcoded line numbers — line numbers drift between commits.
     The agent MUST run this command to find the current location before editing. -->

## Problem

<!-- 1-3 paragraphs: what is wrong and why it matters.
     Include a minimal code snippet showing the CURRENT broken/wrong state if applicable. -->

## Pre-conditions

<!-- Executable checks the agent runs BEFORE writing any code.
     If any fail, the subtask is not ready — check dependencies or report. -->

```bash
# Example: confirm the pattern still exists
grep -n "broken_pattern" platform-backend/orchestrator/path/to/file.py
# Expected: at least 1 match
```

## Fix

<!-- Step-by-step instructions. Show BEFORE/AFTER code when the change is non-trivial.
     Always start with: "Read the file before editing to confirm the current state." -->

Read `path/to/file.py` before editing to confirm the current state.

<!-- If the fix has multiple valid approaches, pick one and label it clearly.
     Use Option A / Option B only when a human decision is genuinely required. -->

## Anti-patterns

<!-- What NOT to do. List 2-3 common mistakes an agent might make on this subtask.
     Omit this section for trivial cleanup subtasks (e.g., removing unused imports). -->

- Do NOT ...
- Do NOT ...

## Post-conditions

<!-- Executable checks the agent runs AFTER completing the fix.
     These must all pass before the subtask can be marked Done. -->

```bash
# Example: confirm the broken pattern is gone
grep -n "broken_pattern" platform-backend/orchestrator/path/to/file.py
# Expected: 0 matches
```

## Tests

<!-- Targeted test commands, then full suites (always required). -->

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test <app>.tests

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run
```

<!-- If new tests must be written, specify exact assertions:
     - Input → Expected output / status code
     - Edge cases to cover
     - What a passing state looks like -->

## Files Changed

```
path/to/file1.py
path/to/file2.py
```

## Rollback

```bash
git revert HEAD
```

<!-- For multi-file changes, note if revert is safe or if ordering matters.
     For schema migrations, note if a reverse migration exists. -->

## Commit Message

```
<type>: <imperative summary>
```

<!-- Use conventional commit types: fix, feat, refactor, docs, chore, test.
     The agent uses this exact string — keep it under 72 characters. -->
