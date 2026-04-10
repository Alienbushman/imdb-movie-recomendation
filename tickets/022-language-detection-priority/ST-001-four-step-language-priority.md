---
id: ST-001
ticket: "022"
title: "4-step language detection priority chain"
priority: Medium
risk: low
status: Open
dependencies: []
subsystems: [backend]
---

# ST-001 — 4-step language detection priority chain

**Priority:** Medium
**Risk:** Low
**Files:** `app/services/candidates.py`

## Problem

`_load_language_data` resolves a title's primary language by taking the mode of
`_resolved` (explicit BCP-47 code OR region-inferred language) across all
`isOriginalTitle=1` rows. Two patterns cause non-English films to resolve as English:

1. `XWW` (worldwide) rows with `isOriginalTitle=1` map to English via `_REGION_TO_LANG`
   and inflate the English vote count.
2. English-speaking regions (US, GB, AU, CA, NZ, IE, ZA) legitimately appear in
   `isOriginalTitle=1` for localized releases of foreign films.
3. The fallback (mode over ALL rows) is even more English-biased because popular
   non-English films have many US/GB/AU/XWW AKA entries.

## Pre-conditions

```bash
grep -n "_ENGLISH_REGIONS" app/services/candidates.py
# Expected: 0 matches (constant does not exist yet)

grep -n "s.mode().iloc\[0\]" app/services/candidates.py
# Expected: at least 2 matches (current mode aggregation)
```

## Fix

1. Read `app/services/candidates.py`, locate `_AMBIGUOUS_REGIONS` (around line 190).

2. Add `_ENGLISH_REGIONS` immediately after `_AMBIGUOUS_REGIONS`:

```python
_ENGLISH_REGIONS: frozenset[str] = frozenset({
    "US", "GB", "AU", "CA", "NZ", "IE", "ZA", "XWW",
})
```

3. In `_load_language_data`, replace the two-pass block (currently starting with the
   comment `# Language: prefer explicit language code over region mapping...` and ending
   after the fallback `lang_by_title.update(fallback)`) with the 4-step chain below.

   The block to replace ends just before `all_langs_by_title = ...`.

**BEFORE** (lines ~589–616):
```python
    # Language: prefer explicit language code over region mapping, prefer original rows
    akas["_lang"] = akas["language"].map(_LANG_CODE_TO_NAME)
    akas["_region_lang"] = akas["region"].map(_REGION_TO_LANG)
    akas.loc[akas["region"].isin(_AMBIGUOUS_REGIONS), "_region_lang"] = None
    akas["_resolved"] = akas["_lang"].fillna(akas["_region_lang"])
    akas = akas.dropna(subset=["_resolved"])
    akas["_is_orig"] = (akas["isOriginalTitle"] == "1").astype(int)

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

**AFTER**:
```python
    # Language: prefer explicit language code over region mapping, prefer original rows
    akas["_lang"] = akas["language"].map(_LANG_CODE_TO_NAME)
    akas["_region_lang"] = akas["region"].map(_REGION_TO_LANG)
    akas.loc[akas["region"].isin(_AMBIGUOUS_REGIONS), "_region_lang"] = None
    akas["_resolved"] = akas["_lang"].fillna(akas["_region_lang"])
    akas = akas.dropna(subset=["_resolved"])
    akas["_is_orig"] = (akas["isOriginalTitle"] == "1").astype(int)

    # Step 1: explicit BCP-47 language code from isOriginalTitle=1 rows (most reliable)
    lang_by_title: dict[str, str] = (
        akas[(akas["_is_orig"] == 1) & akas["_lang"].notna()]
        .groupby("titleId")["_lang"]
        .agg(lambda s: s.mode().iloc[0])
        .to_dict()
    )

    # Step 2: non-English, non-ambiguous region from isOriginalTitle=1 rows
    # (_region_lang is already None for _AMBIGUOUS_REGIONS due to the mask above)
    remaining = title_ids - lang_by_title.keys()
    if remaining:
        step2 = (
            akas[
                (akas["_is_orig"] == 1)
                & akas["titleId"].isin(remaining)
                & akas["_region_lang"].notna()
                & ~akas["region"].isin(_ENGLISH_REGIONS)
            ]
            .groupby("titleId")["_region_lang"]
            .agg(lambda s: s.mode().iloc[0])
            .to_dict()
        )
        lang_by_title.update(step2)

    # Step 3: explicit BCP-47 language code from ALL rows (sparse but accurate)
    remaining = title_ids - lang_by_title.keys()
    if remaining:
        step3 = (
            akas[akas["titleId"].isin(remaining) & akas["_lang"].notna()]
            .groupby("titleId")["_lang"]
            .agg(lambda s: s.mode().iloc[0])
            .to_dict()
        )
        lang_by_title.update(step3)

    # Step 4: full mode fallback — last resort, same as prior behaviour
    remaining = title_ids - lang_by_title.keys()
    if remaining:
        step4 = (
            akas[akas["titleId"].isin(remaining)]
            .groupby("titleId")["_resolved"]
            .agg(lambda s: s.mode().iloc[0])
            .to_dict()
        )
        lang_by_title.update(step4)
```

## Anti-patterns

- Do NOT change `_REGION_TO_LANG`, `_LANG_CODE_TO_NAME`, or `_AMBIGUOUS_REGIONS` — only
  add `_ENGLISH_REGIONS`.
- Do NOT remove the `_resolved` column or the `dropna` on it — `all_langs_by_title` and
  step 4 both depend on it.
- Do NOT change the `CandidateTitle` schema — `language` type stays `str | None`.

## Post-conditions

```bash
grep -n "_ENGLISH_REGIONS" app/services/candidates.py
# Expected: at least 2 matches (definition + usage in step 2)

grep -n "Step 1\|Step 2\|Step 3\|Step 4" app/services/candidates.py
# Expected: 4 matches
```

## Tests

```bash
uv run ruff check app/
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
fix: 4-step language priority chain to reduce English misclassification
```

## Gotchas

- After landing this change, `data/cache/imdb_candidates.json` must be deleted and the
  pipeline re-run to rebuild with corrected language data. The subtask does NOT delete
  the cache file — that is a Hard Stop List item (ask the user).
- `_lang` is the explicit BCP-47 column; `_region_lang` is the region-inferred column;
  `_resolved` is `_lang.fillna(_region_lang)`. Step 1 and 3 use `_lang`; step 2 uses
  `_region_lang`; step 4 uses `_resolved`.
