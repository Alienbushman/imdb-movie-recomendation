---
id: "014"
title: "Documentation Audit"
status: open
priority: medium
component: docs
files_affected:
  - CLAUDE.md
  - frontend/README.md
  - app/services/scored_store.py
  - app/services/features.py
  - app/services/recommend.py
  - app/services/candidates.py
---

# TICKET-014: Documentation Audit

---

## Summary

A full audit of all project documentation revealed several gaps and staleness issues that
have accumulated across tickets 009–013 (person browse, similar titles, frontend
modularization, startup improvements). Fix all discrepancies so documentation accurately
reflects the current codebase.

---

## Problem Details

The audit (run 2026-04-07) identified four categories of issues:

### 1. Missing API endpoints in CLAUDE.md

CLAUDE.md's endpoint table lists 10 endpoints. The API actually has 16. Five endpoints
added in tickets 009–011 are entirely missing from the table:

| Missing endpoint | Ticket that added it |
|---|---|
| `GET /search` | 009 (title search for similar flow) |
| `GET /similar/{imdb_id}` | 009 |
| `GET /people/search` | 011 |
| `GET /people/{name_id}` | 011 |
| `POST /recommendations/filter` | post-005 (re-filter cached results) |

### 2. Missing service in architecture list

`app/services/similar.py` is not mentioned anywhere in CLAUDE.md's architecture section
or file structure diagram. It was added in ticket 009.

`app/main.py` is also absent from the file structure diagram despite being the FastAPI
entry point.

### 3. Frontend README is boilerplate

`frontend/README.md` contains the generic Nuxt Minimal Starter template. It does not
describe the actual project. Real frontend documentation lives in `frontend/CLAUDE.md`,
which is accurate and up to date.

### 4. Underdocumented Python services

Four large service modules have no module-level docstring explaining their purpose or
design. `app/services/candidates.py` (1,000+ lines), `app/services/features.py`,
`app/services/recommend.py`, and `app/services/scored_store.py` all lack a module-level
description that would orient a new reader.

---

## Subtasks

| # | File | Title | Effort | Depends On |
|---|------|-------|--------|------------|
| 1 | [ST-001-fix-claude-md.md](014-documentation-audit/ST-001-fix-claude-md.md) | Fix CLAUDE.md: endpoint table + architecture list | low | — |
| 2 | [ST-002-frontend-readme.md](014-documentation-audit/ST-002-frontend-readme.md) | Rewrite frontend/README.md | low | — |
| 3 | [ST-003-service-docstrings.md](014-documentation-audit/ST-003-service-docstrings.md) | Add module-level docstrings to underdocumented services | low | — |
| 4 | [ST-004-startup-and-datasets.md](014-documentation-audit/ST-004-startup-and-datasets.md) | Document startup sequence and IMDB dataset files in CLAUDE.md | low | ST-001 |

---

## Acceptance Criteria

- [ ] CLAUDE.md endpoint table lists all 16 endpoints (no omissions)
- [ ] CLAUDE.md architecture section lists `similar.py` and `app/main.py`
- [ ] `frontend/README.md` describes the actual project, not the Nuxt boilerplate
- [ ] `app/services/scored_store.py`, `features.py`, `recommend.py`, `candidates.py` each have a module-level docstring
- [ ] CLAUDE.md documents the startup sequence (entry point, cache invalidation, background download)
- [ ] Lint passes: `uv run ruff check app/`
- [ ] Smoke tests pass: `uv run pytest tests/ -q`

---

## Non-Goals

- No changes to any runtime code beyond adding docstrings to service modules
- No restructuring of the ticket system or PROTOCOL.md
- No changes to `config.yaml`
- No new features or refactors
