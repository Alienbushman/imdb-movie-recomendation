---
ticket: "002"
subtask: 1
title: "Backend: IMDB URL Scraper Service"
status: open
effort: low
component: backend
depends_on: []
files_modified: []
files_created:
  - app/services/scrape.py
---

# SUBTASK 01: Backend — Create IMDB URL Scraper Service

---

## Objective

Create a new service module that accepts an IMDB ratings URL or user ID, validates it, and fetches the CSV export from IMDB's export endpoint.

## Context

- IMDB's CSV export endpoint pattern: `https://www.imdb.com/user/{userId}/ratings/export`
- The user ID format is `ur` followed by digits (e.g. `ur38228117`)
- Input URLs look like: `https://www.imdb.com/user/ur38228117/ratings/`
- `httpx` is already in `pyproject.toml` — use it for HTTP requests
- The fetched CSV has the same format as a manually exported IMDB ratings file

## Implementation

Create `app/services/scrape.py` with the following:

### 1. User ID Extraction

```python
import re

_USER_ID_PATTERN = re.compile(r"ur\d+")

def _extract_user_id(imdb_url: str) -> str:
    """Extract IMDB user ID from a URL or raw ID string.
    
    Accepts:
      - Full URL: https://www.imdb.com/user/ur38228117/ratings/
      - Short URL: imdb.com/user/ur38228117
      - Raw ID: ur38228117
    
    Raises ValueError if no valid user ID found.
    """
```

### 2. CSV Fetcher

```python
import httpx

def fetch_imdb_ratings_csv(imdb_url: str, timeout: float = 60.0) -> str:
    """Fetch IMDB ratings CSV for a user.
    
    Args:
        imdb_url: IMDB user ratings URL or user ID
        timeout: HTTP request timeout in seconds
    
    Returns:
        CSV content as a string
    
    Raises:
        ValueError: Invalid URL or user ID format
        RuntimeError: IMDB returned an error (403, 404, etc.) with descriptive message
    """
```

Key implementation details:
- Use `httpx.Client` (synchronous) since the pipeline runs synchronously
- Set browser-like headers:
  ```python
  headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept": "text/csv,text/plain,*/*",
      "Accept-Language": "en-US,en;q=0.9",
  }
  ```
- Build export URL: `f"https://www.imdb.com/user/{user_id}/ratings/export"`
- Handle HTTP errors with descriptive messages:
  - 403 → "IMDB blocked the request. Ratings may be private or authentication is required."
  - 404 → "User not found. Check the IMDB URL."
  - Other → Include status code in error message
- Validate the response looks like a CSV (check for expected header columns: `Const`, `Your Rating`)

### 3. CSV Saver (optional helper)

```python
from pathlib import Path

def save_ratings_csv(csv_content: str, dest: Path) -> None:
    """Save fetched CSV content to disk for caching."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(csv_content, encoding="utf-8")
```

## Acceptance Criteria

- [ ] `_extract_user_id` correctly parses full URLs, short URLs, and raw user IDs
- [ ] `_extract_user_id` raises `ValueError` for invalid inputs
- [ ] `fetch_imdb_ratings_csv` sends request with browser-like headers
- [ ] `fetch_imdb_ratings_csv` returns CSV string on success
- [ ] `fetch_imdb_ratings_csv` raises `RuntimeError` with descriptive message on HTTP errors
- [ ] `fetch_imdb_ratings_csv` validates response contains expected CSV headers
- [ ] `save_ratings_csv` writes content to disk, creating parent directories as needed
- [ ] No new dependencies added (uses existing `httpx`)

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
