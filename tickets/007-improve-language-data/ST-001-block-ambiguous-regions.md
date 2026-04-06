---
id: ST-001
ticket: "007"
title: "Block Region Fallback for Multilingual Countries"
priority: High
risk: low
status: Done
dependencies: []
subsystems: [backend]
---

# ST-001 — Block Region Fallback for Multilingual Countries

**Priority:** High
**Risk:** Low
**Files:** `app/services/candidates.py`

## Problem

`_load_language_data()` maps region codes to a single language via `_REGION_TO_LANG`, then
uses this as a fallback when a title has no explicit `language` code on its `title.akas` rows.
This breaks for multilingual countries: a Tamil film from India (`IN`) with no explicit language
code gets labelled "Hindi", producing false positives for `language=Hindi` filters and wrong
exclusions for `exclude_languages=["Hindi"]`.

## Pre-conditions

```bash
# Confirm _REGION_TO_LANG exists with IN mapping
grep -n '"IN"' app/services/candidates.py
# Expected: at least 1 match showing "IN": "Hindi" or similar

# Confirm _load_language_data function exists
grep -n "def _load_language_data" app/services/candidates.py
# Expected: 1 match

# Confirm _region_lang is used
grep -n "_region_lang" app/services/candidates.py
# Expected: at least 1 match
```

## Fix

Read `app/services/candidates.py` before editing to confirm the current state.

### Step 1 — Add `_AMBIGUOUS_REGIONS` constant (near `_REGION_TO_LANG`)

```python
_AMBIGUOUS_REGIONS: frozenset[str] = frozenset({
    "IN",  # Hindi, Tamil, Telugu, Malayalam, Kannada, ...
    "BE",  # French and Dutch (Flemish)
    "CH",  # German, French, Italian
    "CA",  # English and French
    "NG",  # Hausa, Yoruba, Igbo, English, ...
    "ZW",  # Shona, Ndebele, English, ...
})
```

### Step 2 — Zero out `_region_lang` for ambiguous regions

After the existing line `akas["_region_lang"] = akas["region"].map(_REGION_TO_LANG)`, add:

```python
akas.loc[akas["region"].isin(_AMBIGUOUS_REGIONS), "_region_lang"] = None
```

This ensures the region fallback is silenced for ambiguous countries before the `fillna` merge.

## Anti-patterns

- Do NOT remove entries from `_REGION_TO_LANG` — they are still correct as explicit mappings
  for unambiguous uses. Only the fallback for ambiguous regions should be blocked.
- Do NOT change the `fillna` logic or the `_resolved` column derivation — only the input
  to `fillna` changes for ambiguous regions.

## Post-conditions

```bash
# Confirm _AMBIGUOUS_REGIONS is defined
grep -n "_AMBIGUOUS_REGIONS" app/services/candidates.py
# Expected: at least 2 matches (definition + usage)

# Confirm the isin filter is applied
grep -n "isin(_AMBIGUOUS_REGIONS)" app/services/candidates.py
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
fix: block region fallback for multilingual countries in language resolution
```
