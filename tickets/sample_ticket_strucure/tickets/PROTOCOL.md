# Agent Execution Protocol

Global rules for AI agents executing tickets. Read once at the start of each session.
For allowed commands and hard constraints, see [`../AGENTS.md`](../AGENTS.md).

---

## Session Start

1. Read this file (you are reading it now)
2. Read `../AGENTS.md` — allowed commands and constraints
3. Open the ticket's `PROGRESS.md` — find the first subtask with status `Open`
   - If a subtask is `In Progress`, that is yours (a prior session was interrupted)
   - If all subtasks are `Done`, the ticket is complete — stop
4. Check dependencies — if the subtask lists dependencies, verify they are `Done` in PROGRESS.md
5. Read the subtask file top to bottom
6. Read every file the subtask will modify — never trust line numbers without verifying

---

## Pre-Flight Checks

Both suites must be green before you write any code:

```bash
cd platform-backend/orchestrator && python manage.py test
cd platform-frontend && npx vitest run
```

If either is already failing, stop and report — do not proceed on a broken baseline.

---

## Execution Rules

- Execute subtask steps in the exact numbered order
- When a subtask provides BEFORE/AFTER code, use the exact code shown unless the subtask says to adapt
- After each file modification, verify the change was applied correctly before proceeding
- Do not add features, refactor, or clean up code beyond what the subtask specifies

---

## One Subtask Per Session

- Complete exactly one subtask per session
- Commit, update PROGRESS.md, and stop
- Do not begin the next subtask unless explicitly told to continue
- Subtasks within a ticket should be done in PROGRESS.md row order unless dependencies allow otherwise

---

## Testing

Every subtask has a `## Tests` section with targeted commands. Always also run the full suites:

```bash
# Targeted (as specified in the subtask)
cd platform-backend/orchestrator && python manage.py test <app>.tests

# Full suites (required for every subtask)
cd platform-backend/orchestrator && python manage.py test
cd platform-frontend && npx vitest run
```

Both must pass with zero new failures before marking done.

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

Each subtask file has a `## Commit Message` section. Use that exact string:

```bash
# Stage only the files listed in "## Files Changed"
git add platform-backend/orchestrator/path/to/file.py

# Commit with the exact message from the subtask
git commit -m "$(cat <<'EOF'
<paste exact message from subtask>

Co-Authored-By: Claude <model> <noreply@anthropic.com>
EOF
)"

# Verify
git log --oneline -3
```

- Never use `git add -A` or `git add .`
- Always create new commits — never amend
- Never push unless the user explicitly says to

---

## PROGRESS.md Update

After committing:

1. Change the subtask status to `Done`
2. Add the date and any notes
3. Update the completion counter
4. Commit:
   ```bash
   git add tickets/<ticket-folder>/PROGRESS.md
   git commit -m "chore: mark <ST-NNN> done in PROGRESS.md"
   ```

Then stop.

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
| `docker compose down -v` | Destroys data volumes |
| `python manage.py flush` | Wipes the database |
| `rm -rf` on any directory | Irreversible |
| Deleting `.pkl` or `_format.csv` files | Destroys trained models |
| Editing `middleware/auth.global.ts` | Auth gate — high blast radius |
| Skipping a test failure | Masks regressions |
