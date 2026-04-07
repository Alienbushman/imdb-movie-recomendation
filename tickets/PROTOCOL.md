# Agent Execution Protocol

Global rules for AI agents executing tickets. Read once at the start of each session.
For project-level constraints and development commands, see [`../CLAUDE.md`](../CLAUDE.md).

---

## Session Start

1. Read this file (you are reading it now)
2. Read `../CLAUDE.md` — project structure, dev commands, gotchas
3. Open `tickets/index.yaml` — find your ticket and the first subtask with status `open`
   - If a subtask is `in_progress`, that is yours (a prior session was interrupted)
   - If all subtasks are `done`, the ticket is complete → go to step 8
4. **Set status to `in_progress`** in `index.yaml` — both the subtask and the parent ticket
   (parent ticket moves from `open` → `in_progress`; skip if already `in_progress`)
5. Check dependencies — if the subtask lists dependencies, verify they are `done` in `index.yaml`
6. Read the subtask file top to bottom
7. Read every file the subtask will modify — never trust line numbers without verifying
8. **When the ticket is complete** (all subtasks `done`): rebuild Docker and verify — see
   **Post-Ticket Completion: Docker Rebuild & Verification** below. This step is mandatory.

---

## Pre-Flight Checks

Both suites must be green before you write any code:

```bash
uv run ruff check app/
uv run pytest tests/ -q
cd frontend && npx nuxt typecheck
```

If any check is already failing, stop and report — do not proceed on a broken baseline.

---

## Execution Rules

- Execute subtask steps in the exact numbered order
- When a subtask provides BEFORE/AFTER code, use the exact code shown unless the subtask says to adapt
- After each file modification, verify the change was applied correctly before proceeding
- Do not add features, refactor, or clean up code beyond what the subtask specifies

---

## One Ticket Per Session

- Work on exactly **one ticket** per session — do not jump across tickets
- Within that ticket, complete as many subtasks as possible in PROGRESS.md row order (respecting dependencies)
- After each subtask: update PROGRESS.md and `index.yaml` status, then continue to the next eligible subtask — **do not commit between subtasks**
- Stop when all subtasks in the ticket are `Done`, or when no remaining subtask has its dependencies met
- **Commit once at the end** — after all subtasks are complete — see **Commit Protocol** below

---

## Testing

Every subtask has a `## Tests` section with targeted commands. Always also run the full suites:

```bash
# Backend lint
uv run ruff check app/

# Backend tests
uv run pytest tests/ -q

# Frontend types (if frontend files changed)
cd frontend && npx nuxt typecheck
```

All must pass with zero new failures before marking done.

---

## Pre-conditions and Post-conditions

Subtask files may include `## Pre-conditions` and `## Post-conditions` sections with
executable checks. These are required steps, not suggestions:

- **Pre-conditions**: Run before starting. If any fail, the subtask is not ready — check
  dependencies or report the issue.
- **Post-conditions**: Run after completing all steps. If any fail, the subtask is not done.

---

## Failure Protocol

If any step fails:

1. **Stop immediately.** Do not move to the next step.
2. Report the exact error message or failure output.
3. Do not attempt workarounds not described in the subtask file.
4. Do not skip or comment out tests to make the suite pass.
5. Ask the user for guidance.

---

## Commit Protocol

Commit **once per ticket** — after all subtasks are complete, not after each subtask.

```bash
# Stage all files changed across all subtasks (union of every subtask's "## Files Changed" list,
# plus tickets/index.yaml and tickets/<ticket-folder>/PROGRESS.md)
git add app/services/example.py tickets/index.yaml tickets/NNN-slug/PROGRESS.md

# Write a single commit message that summarises the whole ticket.
# Use the commit messages from individual subtasks as the body if helpful.
git commit -m "$(cat <<'EOF'
<ticket-level summary line>

- ST-001: <subtask commit message>
- ST-002: <subtask commit message>
...

Co-Authored-By: Claude <model> <noreply@anthropic.com>
EOF
)"

# Verify
git log --oneline -3
```

- Never use `git add -A` or `git add .`
- Always create new commits — never amend
- Never push unless the user explicitly says to
- Run `git add` and `git commit` directly — do NOT ask the user for confirmation before committing

---

## PROGRESS.md Update

After completing each subtask (before moving to the next one):

1. In `index.yaml`: set the completed subtask status to `done`
2. In `index.yaml`: set the next eligible subtask status to `in_progress` (or leave the ticket `in_progress` if no more subtasks are ready)
3. In the ticket's `PROGRESS.md`: change the subtask status to `Done`, add the date and any notes, update the completion counter

**Do not commit yet.** These file edits will be included in the single ticket-end commit.

When the ticket is complete, set the ticket status to `done` in `index.yaml`, then commit (see **Commit Protocol** above), then **always** run the Docker rebuild + verification step below before finishing.

---

## Post-Ticket Completion: Docker Rebuild & Verification

**This is a required, non-optional step.** When **all subtasks in a ticket are Done**,
rebuild the running Docker environment so the changes are live. Do not mark a ticket
complete or end the session until the rebuild succeeds and the health checks pass.

```bash
# Rebuild and restart both services
docker compose up --build -d
```

After the containers are up, take any additional steps needed for the changes to take
effect at runtime. Common examples (apply whichever are relevant to the ticket):

| Change type | Required follow-up |
|---|---|
| Schema change to `CandidateTitle` | Delete `data/cache/imdb_candidates.json` before rebuild (ask user first per Hard Stop List) |
| Feature vector / model change | Delete `data/cache/scored_candidates.db` and `data/taste_model.pkl` before rebuild (ask user first) |
| New Python dependency | Ensure `pyproject.toml` is updated — Docker build will install it |
| New frontend dependency | Ensure `package.json` is updated — Docker build will install it |
| Config schema change | Verify `config.yaml` is compatible |
| Database migration / schema change | Delete or migrate the affected DB file before rebuild (ask user first) |

After the rebuild, verify the services are healthy:

```bash
# Check containers are running
docker compose ps

# Smoke-test the API
curl -s http://localhost:8562/api/v1/status | head -20

# Check frontend is reachable
curl -s -o /dev/null -w "%{http_code}" http://localhost:9137
```

If any service fails to start, check logs with `docker compose logs <service>` and fix
before marking the ticket complete.

---

## Recording Decisions and Issues

After completing each subtask, log anything non-obvious in `tickets/NNN-slug/decisions.md`.

Use two distinct sections:

**`## Decisions`** — implementation choices that were not obvious from the spec:
- Why you picked one approach over another
- Trade-offs you evaluated
- Constraints that shaped the implementation

**`## Future Improvements`** — issues, limitations, or follow-on work uncovered during execution:
- Bugs or edge cases noticed but out of scope for this subtask
- Tech debt introduced by this change
- Follow-on tickets that should be created
- Anything that would have been done differently with more time or scope

If neither section exists in the file yet, create it. Keep entries brief — one or two sentences each is enough.

---

## Decision-Required Subtasks

Subtasks marked `⚠️ Decision required` in PROGRESS.md present options. If the subtask
states a preferred option, use it. If no preference is stated, stop and ask the user.

---

## Hard Stop List

Always ask the user before doing any of these, even if a subtask seems to imply it:

| Action | Why |
|---|---|
| `git push` | User controls remote |
| `rm -rf` on any directory | Irreversible |
| Deleting `data/cache/*.json` or `data/cache/*.db` | Destroys cached pipeline data |
| Deleting `data/taste_model.pkl` | Destroys trained model |
| Deleting `data/watchlist.csv` | Destroys user ratings |
| Editing `config.yaml` values | Changes model behaviour globally |
| Adding new Python dependencies | Must be reviewed for compatibility |
| Skipping a test failure | Masks regressions |
