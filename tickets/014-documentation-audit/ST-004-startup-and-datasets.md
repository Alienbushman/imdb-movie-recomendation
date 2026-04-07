---
id: ST-004
ticket: "014"
title: "Document startup sequence and IMDB dataset files in CLAUDE.md"
priority: Low
risk: zero
status: Open
dependencies: [ST-001]
subsystems: [docs]
---

# SUBTASK 04 — Document startup sequence and IMDB dataset files

---

## Objective

Two things are undocumented in `CLAUDE.md` after ST-001:

1. **Startup sequence** — `app/main.py` now appears in the file structure but its
   startup behavior (`invalidate_stale_cache` + background download thread) isn't
   explained anywhere.

2. **Dataset file inventory** — `title.akas.tsv.gz` and `title.crew.tsv.gz` appear
   in `config.yaml` and are loaded by `candidates.py`, but are not mentioned in any
   documentation. The other four files are similarly undocumented.

---

## Pre-conditions

Confirm ST-001 is done (`app/main.py` is now in the CLAUDE.md file structure):

```bash
grep "main.py" CLAUDE.md
```

Expected: one line showing `main.py` in the file tree.

---

## Fix

### Step 1 — Startup sequence section

In `CLAUDE.md`, find the `## Key Design Decisions` section. Add a new section
**immediately before** it:

```markdown
## Startup Sequence

`app/main.py` is the FastAPI entry point. On startup (via the `lifespan` context manager):

1. **Cache invalidation** — `invalidate_stale_cache()` runs synchronously. It reads
   the first 16 KB of `data/cache/imdb_candidates.json` and deletes the file if any
   required field (e.g. `is_anime`, `languages`) is absent from the first record. This
   prevents silent stale-cache bugs after schema changes without loading hundreds of MB.

2. **Background dataset download** — a daemon thread starts `download_datasets()`, which
   fetches any missing IMDB TSV files from `datasets.imdbws.com`. The server is fully
   responsive during this download; the background thread's state is exposed via the
   `datasets_downloading` flag on `GET /status`.

The server is ready to handle requests immediately after step 1, even if datasets are
still downloading.
```

### Step 2 — IMDB dataset inventory

In `CLAUDE.md`, find the `data/datasets/` line in the Project Structure section.
Expand it from a one-liner to a short sub-list:

Replace:
```
│   ├── datasets/           # IMDB bulk TSV files (~1GB total)
```

With:
```
│   ├── datasets/           # IMDB bulk TSV files (~1GB total, auto-downloaded)
│   │   ├── title.basics.tsv.gz      # Title metadata: type, year, runtime, genres
│   │   ├── title.ratings.tsv.gz     # IMDB vote count and average rating
│   │   ├── title.principals.tsv.gz  # Cast/crew associations per title
│   │   ├── name.basics.tsv.gz       # Person names for principal lookup
│   │   ├── title.akas.tsv.gz        # Alternate titles/regions (language inference)
│   │   └── title.crew.tsv.gz        # Director and writer IDs per title
```

---

## Post-conditions

Verify the new section exists:

```bash
grep -c "Cache invalidation" CLAUDE.md
grep -c "title.akas" CLAUDE.md
```

Expected: `1` for each.

---

## Tests

```bash
uv run ruff check app/   # no Python files changed, expect clean
uv run pytest tests/ -q  # no code changed, expect clean
```

---

## Files Changed

- `CLAUDE.md`

---

## Commit Message

```
docs: document startup sequence and IMDB dataset inventory in CLAUDE.md (ST-004)
```
