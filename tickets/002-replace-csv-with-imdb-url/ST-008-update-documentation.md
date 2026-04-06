---
ticket: "002"
subtask: 8
title: "Documentation: Update CLAUDE.md"
status: open
effort: low
component: docs
depends_on: [1, 2, 3, 4, 5, 6, 7]
files_modified:
  - CLAUDE.md
files_created: []
---

# SUBTASK 08: Documentation — Update CLAUDE.md

---

## Objective

Update `CLAUDE.md` to reflect the new URL-based and upload-based watchlist ingestion flow introduced by TICKET-002.

## Changes Required

### 1. Update the Project Structure section

The `data/watchlist.csv` entry already exists. Add a note that it can now be populated via the frontend (URL fetch or file upload), not just manual placement:

```
│   ├── watchlist.csv       # User's IMDB ratings (populated via URL fetch, CSV upload, or manual placement)
```

Add the new service file to the structure:

```
│       ├── scrape.py       # Fetches IMDB ratings CSV from user URL
```

### 2. Update the Recommendation Pipeline section

Update step 1 to reflect both data acquisition paths:

```
1. **Ingest** → Acquire ratings via one of three paths:
   - IMDB URL fetch: backend scrapes `https://www.imdb.com/user/{id}/ratings/export`
   - CSV upload: user uploads manually exported file via `POST /upload-watchlist`
   - Local file: reads `data/watchlist.csv` directly (legacy / Docker workflow)
   Then parse into `RatedTitle` objects.
```

### 3. Update the API Endpoints table

Add the new upload endpoint:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/upload-watchlist` | Accept manually exported IMDB ratings CSV |

Update the `/recommendations` row to note the new `imdb_url` query param:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/recommendations` | Run full pipeline; optional `imdb_url` query param to fetch ratings from IMDB |

### 4. Update the Key Design Decisions section

Add a new bullet:

```
- **Watchlist acquisition** — Three supported paths: IMDB URL (server-side HTTP fetch to the user's public export endpoint), CSV upload (multipart POST), or pre-placed local file. The URL fetch saves the result to `data/watchlist.csv` so subsequent runs without a URL still work.
```

## Acceptance Criteria

- [ ] `scrape.py` listed in project structure
- [ ] `watchlist.csv` description updated to mention URL/upload sources
- [ ] Pipeline step 1 updated to describe all three acquisition paths
- [ ] API endpoints table includes `POST /upload-watchlist`
- [ ] `POST /recommendations` notes `imdb_url` query param
- [ ] Key Design Decisions updated with watchlist acquisition bullet

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
