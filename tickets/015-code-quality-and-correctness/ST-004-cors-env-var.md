---
id: ST-004
ticket: "015"
title: "CORS allowed origins via env var"
priority: Low
risk: zero
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 04 — CORS allowed origins via env var

---

## Objective

`app/main.py` hardcodes `allow_origins=["http://localhost:3000", "http://localhost:9137"]`.
Anyone running on a non-localhost server hits CORS errors with no fix short of editing
source. Make the allowed origins configurable via a `CORS_ORIGINS` env var.

Default behaviour (no env var set) must be identical to today.

---

## Pre-conditions

Confirm the hardcoded list:

```bash
grep -n "allow_origins" app/main.py
```

Expected: one match with the two localhost strings.

---

## Fix

### Step 1 — `app/main.py`

Find the import block at the top of the file and add `os` if not already present:

```python
import os
```

Find the hardcoded origins line:

```python
    allow_origins=["http://localhost:3000", "http://localhost:9137"],
```

Replace the entire `CORSMiddleware` `add_middleware` call with:

```python
_cors_origins_env = os.environ.get("CORS_ORIGINS", "")
_cors_origins: list[str] = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else ["http://localhost:3000", "http://localhost:9137"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Place `_cors_origins_env` and `_cors_origins` at module level (outside any
function), immediately before `app.add_middleware(...)`.

---

## Post-conditions

Verify the default (no env var) still produces the two localhost origins:

```bash
python -c "
import os
env = os.environ.get('CORS_ORIGINS', '')
origins = [o.strip() for o in env.split(',') if o.strip()] if env else ['http://localhost:3000', 'http://localhost:9137']
print(origins)
"
```

Expected: `['http://localhost:3000', 'http://localhost:9137']`

Verify custom origins parse correctly:

```bash
CORS_ORIGINS="https://myserver.com,https://other.example.com" python -c "
import os
env = os.environ.get('CORS_ORIGINS', '')
origins = [o.strip() for o in env.split(',') if o.strip()] if env else ['http://localhost:3000', 'http://localhost:9137']
print(origins)
"
```

Expected: `['https://myserver.com', 'https://other.example.com']`

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

---

## Files Changed

- `app/main.py`

---

## Commit Message

```
feat: make CORS allowed origins configurable via CORS_ORIGINS env var (ST-004)
```
