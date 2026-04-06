---
ticket: "005"
subtask: 4
title: "Deduplicate name_lookup Load + Partial Cache Invalidation Check"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/candidates.py
files_created: []
---

# SUBTASK 005-04: Deduplicate `name_lookup` Load + Partial Cache Invalidation Check

---

## Context

Two small but measurable inefficiencies in `candidates.py`:

1. **`name.basics.tsv.gz` is loaded twice** — once inside `_load_person_data()`
   (line 301) and again inside `_load_writer_data()` (line 384). Loading
   `name.basics` (12M+ rows) takes ~1–2 s and ~500 MB RAM peak. Loading it
   twice is wasted work.

2. **`invalidate_stale_cache()` loads the entire cache JSON** (potentially
   hundreds of MB) just to inspect one field on the first object. A 16 KB
   partial read is enough.

---

## Implementation

### 1. Load `name_lookup` once in `load_candidates_from_datasets()`

Change `_load_person_data` and `_load_writer_data` to accept a pre-built
`name_lookup` dict rather than loading it themselves.

**`_load_person_data` signature change:**
```python
def _load_person_data(
    title_ids: set[str],
    name_lookup: dict[str, str],
) -> tuple[...]:
```
Remove the internal `_load_name_lookup(names_path)` call and the
`names_path.exists()` check (caller handles this).

**`_load_writer_data` signature change:**
```python
def _load_writer_data(
    title_ids: set[str],
    name_lookup: dict[str, str],
) -> dict[str, list[str]]:
```
Remove the internal `_load_name_lookup(names_path) if names_path.exists() else {}`
call.

**In `load_candidates_from_datasets()`**, load once before calling either:
```python
names_path = PROJECT_ROOT / ds_cfg.name_basics
name_lookup: dict[str, str] = {}
if names_path.exists():
    name_lookup = _load_name_lookup(names_path)
else:
    logger.warning("name.basics not found — person names will be unavailable")

actors_by_title, directors_by_title, composers_by_title, cinematographers_by_title = (
    _load_person_data(candidate_ids | seen_ids, name_lookup)
)
writers_by_title = _load_writer_data(candidate_ids | seen_ids, name_lookup)
```

Remove the `names_path` variable from inside `_load_person_data`
(it previously derived it from `settings`).

### 2. Partial read in `invalidate_stale_cache()`

Replace the full `json.load(f)` with a partial read + `JSONDecoder.raw_decode`:

```python
def invalidate_stale_cache() -> bool:
    path = _cache_path()
    if not path.exists():
        return False
    try:
        with open(path) as f:
            chunk = f.read(16384)          # 16 KB covers any single candidate object
        start = chunk.find("{")            # first object inside the JSON array
        if start == -1:
            raise ValueError("no object found")
        first, _ = json.JSONDecoder().raw_decode(chunk, start)
        missing = _REQUIRED_CACHE_FIELDS - set(first.keys())
        if missing:
            path.unlink()
            logger.info("Deleted stale candidate cache (missing fields: %s)", sorted(missing))
            return True
    except (json.JSONDecodeError, ValueError, KeyError):
        path.unlink()
        logger.info("Deleted corrupt candidate cache")
        return True
    return False
```

No extra dependencies — `json.JSONDecoder` is in the standard library.

---

## Acceptance Criteria

- [x] `_load_name_lookup` is called exactly once per `load_candidates_from_datasets()` call
- [x] `_load_person_data` and `_load_writer_data` accept `name_lookup` as a parameter
- [x] `invalidate_stale_cache()` reads at most 16 KB regardless of cache file size
- [x] Existing graceful fallback (missing files → empty dicts) preserved
- [x] `uv run ruff check app/` passes
- [x] `uv run pytest tests/ -q` passes
