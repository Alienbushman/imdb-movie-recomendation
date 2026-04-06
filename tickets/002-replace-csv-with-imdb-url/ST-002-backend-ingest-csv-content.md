---
ticket: "002"
subtask: 2
title: "Backend: Modify Ingest to Accept CSV Content String"
status: open
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/ingest.py
files_created: []
---

# SUBTASK 02: Backend — Modify Ingest to Accept CSV Content String

---

## Objective

Modify `load_watchlist()` in `ingest.py` so it can parse CSV content from a string (passed by the scraper) in addition to reading from a file path.

## Context

Currently `load_watchlist()` only reads from a file path (`data/watchlist.csv`). The function signature is:

```python
def load_watchlist(path: Path | None = None) -> list[RatedTitle]:
```

It calls `pd.read_csv(path)` internally. To support the URL-based flow, the function needs to also accept raw CSV content as a string and parse it via `pd.read_csv(io.StringIO(csv_content))`.

The column mappings, parsing logic, and `RatedTitle` construction remain completely unchanged — only the data source changes.

## Implementation

### Modify `load_watchlist` signature

```python
import io

def load_watchlist(
    path: Path | None = None,
    csv_content: str | None = None,
) -> list[RatedTitle]:
```

### Add CSV content branch at the top of the function

Before the existing `pd.read_csv(path)` call, add:

```python
if csv_content is not None:
    df = pd.read_csv(io.StringIO(csv_content))
elif path is None:
    settings = get_settings()
    path = PROJECT_ROOT / settings.data.watchlist_path
    df = pd.read_csv(path)
else:
    df = pd.read_csv(path)
```

### No other changes needed

All downstream logic (column mapping, type conversion, `RatedTitle` construction) works identically regardless of whether the DataFrame came from a file or a string.

## Acceptance Criteria

- [ ] `load_watchlist(csv_content="...")` parses CSV from string using `io.StringIO`
- [ ] `load_watchlist()` (no args) still reads from default file path — existing behavior preserved
- [ ] `load_watchlist(path=some_path)` still reads from explicit path — existing behavior preserved
- [ ] If both `path` and `csv_content` are provided, `csv_content` takes precedence
- [ ] Import `io` added to the file
- [ ] No other changes to parsing logic, column mappings, or `RatedTitle` construction

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
