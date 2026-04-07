---
id: ST-001
ticket: "014"
title: "Fix CLAUDE.md: endpoint table and architecture list"
priority: Medium
risk: zero
status: Open
dependencies: []
subsystems: [docs]
---

# SUBTASK 01 — Fix CLAUDE.md: endpoint table and architecture list

---

## Objective

Update `CLAUDE.md` so its API endpoint table and architecture section accurately reflect
the current codebase. Five endpoints and two service files were added across tickets
009–011 but never documented.

---

## Pre-conditions

Verify the endpoints actually exist:

```bash
grep -n "@router\." app/api/routes.py | grep -E "search|similar|people|filter"
```

Expected: lines for `/search`, `/similar/{imdb_id}`, `/people/search`, `/people/{name_id}`,
and `/recommendations/filter`.

Verify `similar.py` exists:

```bash
ls app/services/similar.py
```

---

## Fix

### Step 1 — API Endpoints table

In `CLAUDE.md`, find the `## API Endpoints (prefix: \`/api/v1\`)` section and its table.

Add these rows (in a logical grouping — after the existing GET recommendations rows,
before `/dismiss`):

```markdown
| GET | `/search` | Search titles by name |
| GET | `/similar/{imdb_id}` | Find titles similar to a given title |
| GET | `/people/search` | Search directors and actors by name |
| GET | `/people/{name_id}` | Get all titles for a person |
| POST | `/recommendations/filter` | Re-filter cached results without re-running pipeline |
```

Also add `GET /health` (defined in `app/main.py`, not `routes.py`) after the status row:

```markdown
| GET | `/health` | Liveness check (used by Docker healthcheck) |
```

### Step 2 — Services list in Project Structure

Find the `app/services/` block in the `## Project Structure` section. Add `similar.py`
after `recommend.py`:

```
│       ├── similar.py        # Cosine-similarity engine for "find similar titles"
```

### Step 3 — File structure: add app/main.py

In the Project Structure tree, add `app/main.py` immediately before `app/api/`:

```
├── app/                    # Python backend (FastAPI)
│   ├── main.py             # FastAPI entry point, lifespan startup, CORS middleware
│   ├── api/routes.py       # All API endpoints
```

---

## Post-conditions

After edits, verify the endpoint table has exactly 17 rows (including the header):

```bash
grep -c "^|" CLAUDE.md
```

(The table has 17 data rows + 2 header rows = 19 `|`-prefixed lines in that block, but
this count may vary with other tables. Visual inspection is sufficient.)

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
docs: add missing endpoints and services to CLAUDE.md (ST-001)
```
