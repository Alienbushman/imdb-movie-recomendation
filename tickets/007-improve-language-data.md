---
id: "007"
title: "Improve Language Data Quality for Filtering"
status: done
priority: medium
component: backend
files_affected:
  - app/services/candidates.py
  - app/models/schemas.py
  - app/services/scored_store.py
---

# TICKET-007: Improve Language Data Quality for Filtering

---

## Problem

Language filtering (`?language=Hindi`, `exclude_languages=["Korean"]`) relies on the `language`
field populated during `_load_language_data()` in `candidates.py`. That field is derived from
`title.akas` which is noisy and incomplete. Several concrete failure modes exist:

### 1. Lossy region → language fallback for multilingual countries

`_REGION_TO_LANG` maps country codes to a single language:

```python
"IN": "Hindi",   # wrong for Tamil, Telugu, Malayalam, Kannada films
"BE": "French",  # wrong for Flemish (Dutch) films
"CH": "German",  # wrong for French-Swiss and Italian-Swiss films
"CN": "Chinese", # conflates Mandarin and Cantonese
```

A Tamil film like *Vikram* or a Telugu film like *RRR* is produced in India (`IN`) and has no
explicit `language` code on many `title.akas` rows — so it gets labelled "Hindi" via the
region fallback, breaking both the `language=Hindi` include filter (false positive) and the
`exclude_languages=["Hindi"]` exclude filter (wrong exclusion).

### 2. `isOriginalTitle` flag is unreliable

IMDB's crowd-sourced `isOriginalTitle` flag is inconsistently set. Many original-language
rows lack the flag, meaning the current logic (`sort by _is_orig DESC, take first`) may
pick a non-original row as the language source, especially for older or less-edited titles.

### 3. Ambiguous "first" selection when multiple original rows exist

When a title has two `isOriginalTitle=1` rows with different resolved languages, the code
takes `first()` after sorting by `(titleId, _is_orig)`. The secondary sort is undefined,
so the selected language is arbitrary. For bilingual co-productions this produces
non-deterministic results across dataset rebuilds.

### 4. High null rate — unknown scope

No metrics are logged for how many candidate titles end up with `language=None`. Anecdotally,
a non-trivial fraction of candidates have no usable language data in `title.akas` at all.
Filtering by language silently excludes these titles, so users may get fewer results than
expected without explanation. Until we measure the null rate, we can't prioritise further
improvements.

### 5. Single language stored per title loses multi-language signal

Co-productions and bilingual films are reduced to one language string. A film with
substantial English and French dialogue will be labelled whichever language "wins" the
resolution logic. The `exclude_languages=["English"]` filter will then either correctly
or incorrectly exclude it depending on which label was picked.

---

## Solution

Four targeted fixes in `_load_language_data()`, each independently valuable:

### Fix 1 — Block region fallback for ambiguous countries

Define a set of regions where a single-language mapping is wrong more often than it is
right. For titles from those regions, accept `None` rather than a wrong label.

```python
_AMBIGUOUS_REGIONS = frozenset({
    "IN",  # Hindi, Tamil, Telugu, Malayalam, Kannada, ...
    "BE",  # French and Dutch (Flemish)
    "CH",  # German, French, Italian
    "CA",  # English and French
    "NG",  # Hausa, Yoruba, Igbo, English, ...
    "ZW",  # Shona, Ndebele, English, ...
})
```

In `_load_language_data()`, zero out `_region_lang` for rows whose region is in
`_AMBIGUOUS_REGIONS` before the `fillna`. Explicit `language` codes still work
for these regions — only the fallback is disabled.

### Fix 2 — Use mode instead of first for original-title rows

After filtering to `isOriginalTitle=1` rows, take the **most common** resolved language
per `titleId` rather than the first one. This is more robust to one-off incorrect rows.

```python
# instead of: akas_sorted.groupby("titleId")["_resolved"].first()
lang_by_title = (
    akas[akas["_is_orig"] == 1]
    .dropna(subset=["_resolved"])
    .groupby("titleId")["_resolved"]
    .agg(lambda s: s.mode().iloc[0])  # most common value
    .to_dict()
)
# Fall back to any row for titles with no original-title match
no_orig = set(title_ids) - lang_by_title.keys()
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

### Fix 3 — Log null coverage after resolution

At the end of `_load_language_data()`, add a log line showing the null rate:

```python
null_count = len(title_ids) - len(lang_by_title)
logger.info(
    "  Language null rate: %d / %d titles (%.1f%%) have no language resolved",
    null_count, len(title_ids), 100 * null_count / max(len(title_ids), 1),
)
```

This is a two-line change that immediately makes the scope of the problem visible in
pipeline logs without any schema changes.

### Fix 4 — Store `languages` list alongside primary `language`

Add a `languages: list[str]` field to `CandidateTitle` (all distinct resolved languages
for a title, not just the primary one). Populate it in `load_candidates_from_datasets()`.
Store it as a JSON column in `scored_candidates.db`. This is groundwork for future
"has English audio" style filtering but does not change the current filter behaviour.

**Note:** This requires a candidate cache rebuild (delete `data/cache/imdb_candidates.json`)
and a scored-store rebuild (delete `data/cache/scored_candidates.db`).

---

## What this does NOT fix

- Titles with no `title.akas` rows at all — they will still have `language=None`.
  The root cause is missing IMDB data, not a code issue.
- Cantonese vs Mandarin — both map to "Chinese" at the display level. Distinguishing
  them would require exposing raw BCP-47 codes (`yue` / `cmn`) in the UI, which is
  scope for a separate ticket.
- `isOriginalTitle` unreliability at the row level — Fix 2 (mode) reduces sensitivity
  to bad rows but cannot fully compensate for a title where the majority of
  `isOriginalTitle=1` rows carry a wrong value.

---

## Subtasks

| # | File | Title | Component |
|---|------|-------|-----------|
| 1 | [ST-001-block-ambiguous-regions.md](007-improve-language-data/ST-001-block-ambiguous-regions.md) | Block region fallback for multilingual countries | Backend |
| 2 | [ST-002-mode-aggregation.md](007-improve-language-data/ST-002-mode-aggregation.md) | Use mode instead of first for language resolution | Backend |
| 3 | [ST-003-null-coverage-logging.md](007-improve-language-data/ST-003-null-coverage-logging.md) | Log language null coverage in pipeline | Backend |
| 4 | [ST-004-languages-list-field.md](007-improve-language-data/ST-004-languages-list-field.md) | Add `languages` list field to CandidateTitle | Backend |

### Execution Order

```
Subtask 3 (logging) is independent and safe — do first.
Subtasks 1 and 2 both edit _load_language_data() — do sequentially to avoid conflicts.
Subtask 4 (schema change) requires both 1 and 2 to be merged first.
```

---

## Acceptance Criteria

- [ ] Indian films with explicit Tamil/Telugu/Malayalam/Kannada language codes are no
      longer mislabelled as "Hindi" when filtered by `language=Hindi`
- [ ] Pipeline logs show language null rate (e.g. "Language null rate: 1243 / 11677 (10.6%)")
- [ ] `CandidateTitle.languages` field exists and is populated with all distinct
      resolved languages per title (may be empty list)
- [ ] Existing language filter behaviour is unchanged for unambiguous single-language
      countries (US → English, JP → Japanese, KR → Korean, FR → French)
- [ ] Lint passes: `uv run ruff check app/`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`
- [ ] `data/cache/imdb_candidates.json` deleted and rebuilt after schema change in Subtask 4
