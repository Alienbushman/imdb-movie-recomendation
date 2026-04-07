---
id: ST-002
ticket: "015"
title: "Align min_vote_count code default with config"
priority: Low
risk: zero
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 02 — Align min_vote_count code default with config

---

## Objective

`config.yaml` sets `min_vote_count: 100`, but the Pydantic model in `config.py`
defaults to `10000`. If `config.yaml` is absent or unreadable, the server silently
filters out ~99% of candidates. Align the code default so behaviour degrades
gracefully instead of catastrophically.

---

## Pre-conditions

Confirm the mismatch:

```bash
grep -n "min_vote_count" config.yaml app/core/config.py
```

Expected output:
```
config.yaml:12:  min_vote_count: 100
app/core/config.py:20:    min_vote_count: int = 10000
```

---

## Fix

### Step 1 — `app/core/config.py`

Find the line:

```python
    min_vote_count: int = 10000
```

Replace with:

```python
    min_vote_count: int = 100
```

---

## Post-conditions

```bash
grep -n "min_vote_count" config.yaml app/core/config.py
```

Both values should now be `100`.

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

---

## Files Changed

- `app/core/config.py`

---

## Commit Message

```
fix: align min_vote_count code default with config.yaml (ST-002)
```
