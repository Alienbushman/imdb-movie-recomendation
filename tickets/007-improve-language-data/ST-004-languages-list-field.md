---
id: ST-004
ticket: "007"
title: "Add languages List Field to CandidateTitle"
priority: Medium
risk: medium
status: Done
dependencies: ["ST-001", "ST-002"]
subsystems: [backend]
---

# ST-004 — Add `languages` List Field to CandidateTitle

**Priority:** Medium
**Risk:** Medium (schema change — requires cache invalidation)
**Files:** `app/models/schemas.py`, `app/services/candidates.py`, `app/services/scored_store.py`

## Problem

`CandidateTitle` stores only a single `language` string, which is the primary resolved language.
Co-productions and bilingual films have multiple valid languages, but that signal is discarded.

**Cache invalidation required after this subtask** (confirm with user before deleting — Hard Stop List):
- `data/cache/imdb_candidates.json` — new field on `CandidateTitle`
- `data/cache/scored_candidates.db` — new column in the SQLite schema

## Pre-conditions

```bash
# Confirm ST-001 and ST-002 are applied (mode aggregation exists)
grep -n "mode()" app/services/candidates.py
# Expected: at least 1 match

# Confirm CandidateTitle has language field but no languages field
grep -n "language" app/models/schemas.py
# Expected: matches for "language" but NOT "languages: list"

# Confirm _load_language_data returns two values currently
grep -n "return.*lang_by_title.*country_by_title" app/services/candidates.py
# Expected: 1 match
```

## Fix

Read all three files before editing to confirm the current state.

### Step 1 — `app/services/candidates.py` — return third dict from `_load_language_data()`

After building `lang_by_title`, add:

```python
all_langs_by_title: dict[str, list[str]] = (
    akas.dropna(subset=["_resolved"])
    .groupby("titleId")["_resolved"]
    .agg(lambda s: sorted(s.unique().tolist()))
    .to_dict()
)
```

Update the return statement to include the third value:

```python
return lang_by_title, country_by_title, all_langs_by_title
```

Update the call site in `load_candidates_from_datasets()`:

```python
lang_by_title, country_by_title, all_langs_by_title = _load_language_data(candidate_ids)
```

In the candidate construction loop, populate the new field:

```python
languages=all_langs_by_title.get(tconst, []),
```

### Step 2 — `app/models/schemas.py` — add field to `CandidateTitle`

Add after the existing `language` field:

```python
languages: list[str] = []
```

### Step 3 — `app/services/scored_store.py` — add column to SQLite schema

Add to the `CREATE TABLE` statement:

```sql
languages  TEXT NOT NULL DEFAULT '[]',
```

In `save_scored()`, serialise the field:

```python
json.dumps(getattr(c, "languages", [])),
```

In `query_candidates()`, deserialise:

```python
languages=json.loads(row["languages"] or "[]"),
```

## Anti-patterns

- Do NOT change the existing `language` (singular) field in any way — it must remain
  unchanged in value and behaviour
- Do NOT forget to update `save_scored()` and `query_candidates()` in `scored_store.py` —
  a missing column will cause SQLite errors on the next pipeline run
- Do NOT delete the caches without confirming with the user first (Hard Stop List)

## Post-conditions

```bash
# Confirm languages field exists on CandidateTitle
grep -n "languages.*list" app/models/schemas.py
# Expected: 1 match

# Confirm _load_language_data returns three values
grep -n "all_langs_by_title" app/services/candidates.py
# Expected: at least 2 matches

# Confirm scored_store handles the languages column
grep -n "languages" app/services/scored_store.py
# Expected: at least 2 matches (save + query)
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
app/models/schemas.py
app/services/candidates.py
app/services/scored_store.py
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: add languages list field to CandidateTitle for multi-language support
```

## Gotchas

- After this subtask, `data/cache/imdb_candidates.json` and `data/cache/scored_candidates.db`
  must be deleted to pick up the schema change. The stale cache will silently use the old
  schema without the `languages` field. Confirm deletion with user (Hard Stop List).
