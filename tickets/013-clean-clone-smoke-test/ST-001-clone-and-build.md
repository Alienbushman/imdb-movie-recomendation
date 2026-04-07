---
ticket: "013"
subtask: 1
title: "Clone + Docker Build"
status: Open
effort: low
component: full_stack
depends_on: []
files_modified: []
files_created: []
---

# SUBTASK 01 — Clone to Temp Dir + `docker compose build`

---

## Objective

Clone the project to a clean temporary directory and run `docker compose build`.
Document every error encountered. Do not fix anything yet.

---

## Steps

### 1. Clone to temp directory

```bash
cd /c/tmp
git clone <repo-url> imdb-smoke-test
cd imdb-smoke-test
```

Verify the clone contains no `data/` directory:

```bash
ls -la | grep data
# Expected: no output (data/ is gitignored and empty dirs aren't tracked)
```

### 2. Confirm no pre-existing Docker images for this project

```bash
docker images | grep imdb
```

If images exist from a previous attempt, remove them:

```bash
docker compose down --rmi all 2>/dev/null || true
```

### 3. Run `docker compose build`

```bash
docker compose build 2>&1 | tee /c/tmp/build.log
```

Watch for and record any build failures. Common issues to check:

- Python dependency resolution failures
- `playwright install` not called (Playwright browser binaries missing)
- Missing system packages (`libgomp1`, etc.)
- Frontend `npm install` or `nuxt build` failures
- Any `COPY` steps referencing files not present in the repo

### 4. Record findings

After the build, check the log:

```bash
grep -i "error\|failed\|could not" /c/tmp/build.log | head -40
```

Document all failures in `decisions.md` under the heading `## ST-001 Build Findings`.

---

## Acceptance Criteria

- [ ] Fresh clone exists at `c:/tmp/imdb-smoke-test` with no `data/` directory
- [ ] `docker compose build` output captured to `/c/tmp/build.log`
- [ ] All build errors recorded in `decisions.md`
- [ ] If build succeeds: images exist for both `api` and `frontend` services

---

## Commit Message

```
chore: document clean clone build audit (ST-001)
```

(Commit only `decisions.md` — no code changes in this subtask.)
