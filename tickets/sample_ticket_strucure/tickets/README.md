# Tickets — Agent-Executable Task System

This folder contains all work items for the stock-predictor project. Each ticket is designed
to be picked up and executed by an AI agent (or a human) with minimal ambiguity.

---

## Quick Start (Agents)

1. Read `PROTOCOL.md` — execution rules, commit protocol, failure handling
2. Read `../../AGENTS.md` — allowed commands and hard constraints
3. Pick a ticket folder — read its `ticket.md` for context and `PROGRESS.md` for the next open subtask
4. Read the subtask file top to bottom, then read every file it will modify
5. Execute

---

## Directory Layout

```
tickets/
├── README.md               ← you are here
├── PROTOCOL.md             ← global agent execution rules (read once per session)
├── _templates/
│   ├── ticket.md           ← template for parent tickets
│   └── subtask.md          ← template for subtask files
├── NNN-short-name.md       ← parent ticket (summary + subtask index)
└── NNN-short-name/         ← subtask folder
    ├── PROGRESS.md         ← subtask status tracker
    └── ST-NNN-slug.md      ← individual subtask files
```

---

## Naming Conventions

| Item | Format | Example |
|---|---|---|
| Ticket | `NNN-kebab-case-name` | `001-post-hardening-code-review` |
| Subtask file | `ST-NNN-kebab-case-slug.md` | `ST-003-rolling-window-alignment.md` |
| Ticket numbering | Sequential 3-digit, zero-padded | `001`, `002`, `003` |
| Subtask numbering | Sequential 3-digit within parent ticket | `ST-001`, `ST-002` |

---

## Lifecycle States

| State | Meaning |
|---|---|
| `Open` | Ready to be picked up |
| `In Progress` | An agent is actively working on it |
| `Blocked` | Cannot proceed — dependency or decision needed |
| `Done` | Completed and verified |
| `Won't Do` | Explicitly decided not to do — must have a reason in Notes |

---

## Priority Levels

| Priority | Meaning |
|---|---|
| `Critical` | Security vulnerability or data corruption — do immediately |
| `High` | Correctness bug or missing validation — do before feature work |
| `Medium` | Wrong pattern, code smell, DRY violation — do in normal flow |
| `Low` | Cleanup, cosmetic, nice-to-have — do when convenient |

---

## Creating a New Ticket

1. Copy `_templates/ticket.md` → `tickets/NNN-short-name.md`
2. Create folder `tickets/NNN-short-name/`
3. Copy `_templates/subtask.md` for each subtask → `NNN-short-name/ST-NNN-slug.md`
4. Create `NNN-short-name/PROGRESS.md` with a row per subtask

All sections in the templates are required unless marked `(optional)`. If a section does not
apply, write "N/A" rather than deleting the heading — this keeps the structure scannable.

---

## Relationship to hardening-tasks/

The `hardening-tasks/` folder was the first-generation task system used for the production
hardening initiative (Phases 1–5, now complete). This `tickets/` system is the successor.
Key differences:

- `hardening-tasks/` had a single global PROGRESS.md tracking all phases; `tickets/` scopes
  progress tracking per ticket.
- `hardening-tasks/` embedded agent protocol in both AGENT_PROTOCOL.md and per-task files;
  `tickets/` centralizes it in a single PROTOCOL.md.
- `tickets/` uses YAML frontmatter for machine-readable metadata.
- `tickets/` uses standardized templates to enforce structural consistency.
