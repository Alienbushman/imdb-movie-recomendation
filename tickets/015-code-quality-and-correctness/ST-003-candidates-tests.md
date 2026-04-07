---
id: ST-003
ticket: "015"
title: "Add unit tests for candidates.py"
priority: High
risk: zero
status: Done
dependencies: [ST-001]
subsystems: [backend]
---

# SUBTASK 03 — Add unit tests for candidates.py

---

## Objective

`candidates.py` has zero test coverage despite being the most complex service
(~900 lines). It handles six TSV joins, anime detection, language extraction,
crew enrichment, and the `rated_writers` lookup added in ST-001. Add unit tests
using small in-memory fixtures — no real IMDB dataset files required.

---

## Pre-conditions

Confirm there is no existing candidates test file:

```bash
ls tests/test_candidates.py 2>/dev/null && echo "exists" || echo "missing"
```

Expected: `missing`

Confirm ST-001 is done (writer path exists):

```bash
grep -n "rated_writers" app/services/candidates.py
```

Expected: at least two matches (build line + return line).

---

## Fix

Create `tests/test_candidates.py`. The file must test the following using
synthetic minimal TSV data — do NOT load real dataset files.

The tests should use helpers that call the internal parsing functions directly
where possible, or use `tmp_path` fixtures with small TSV content.

### What to test

**1. `_load_crew_data()` — writer lookup is populated**

Provide a minimal `title.crew.tsv.gz` with two titles: one has a writer, one does
not. Assert:
- `raw_writers` contains the expected tconst → nconst mapping
- A title with `\\N` in the writers column is not in `raw_writers`

**2. `load_candidates_from_datasets()` — `rated_writers` is returned correctly**

This is an integration-level test using `tmp_path`. Provide:
- A minimal `title.basics.tsv.gz` (3–5 rows, mixed title types)
- A minimal `title.ratings.tsv.gz` (matching rows)
- A minimal `title.crew.tsv.gz` (some with writers, some without)
- A minimal `title.principals.tsv.gz` (empty or one row — not the focus here)
- A minimal `name.basics.tsv.gz` (name resolution for writers)
- A minimal `title.akas.tsv.gz` (1–2 rows)

Pass `seen_ids` that includes a tconst that has a known writer. Assert:
- `rated_writers` is a dict
- The seen title's writer name appears in `rated_writers[tconst]`

This test is integration-level and may be slow — mark it with
`@pytest.mark.slow` so it can be excluded if needed.

**3. Anime detection — `is_anime` flag is set correctly**

Provide candidates where one `tconst` is in the anime whitelist (mock or patch
the whitelist lookup). Assert `is_anime=True` for that candidate and `False` for
others.

If the whitelist fetching is too hard to mock, test `_is_anime_by_genre()` or
the genre-based fallback directly.

**4. `_resolve_names()` — nconst to name mapping**

Unit test the name resolution helper directly. Provide a `name_lookup` dict and
a `raw_by_title` dict. Assert resolved names match expectations and missing
nconsts are dropped.

### File structure

```python
# tests/test_candidates.py

import gzip
import io
import pytest
# ... imports as needed

# --- Helpers ---

def make_tsv_gz(rows: list[str]) -> bytes:
    """Build an in-memory gzipped TSV from a list of lines."""
    content = "\n".join(rows).encode()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as f:
        f.write(content)
    return buf.getvalue()


# --- Tests ---

def test_load_crew_data_writers(tmp_path):
    ...

def test_resolve_names():
    ...

def test_rated_writers_returned(tmp_path, monkeypatch):
    ...

@pytest.mark.slow
def test_load_candidates_integration(tmp_path, monkeypatch):
    ...

def test_anime_detection(tmp_path, monkeypatch):
    ...
```

---

## Post-conditions

```bash
uv run pytest tests/test_candidates.py -v
```

All new tests must pass. If `_load_crew_data()` or `_resolve_names()` are private
(prefixed with `_`), import them directly:

```python
from app.services.candidates import _load_crew_data, _resolve_names
```

---

## Tests

```bash
uv run ruff check app/ tests/
uv run pytest tests/ -q
```

---

## Files Changed

- `tests/test_candidates.py` (new file)

---

## Commit Message

```
test: add unit tests for candidates.py crew loading and writer lookup (ST-003)
```
