# Tickets — Agent-Executable Task System

This folder contains all work items for the IMDB Movie Recommendation project. Each ticket
is designed to be picked up and executed by an AI agent (or a human) with minimal ambiguity.

---

## Quick Start (Agents)

1. Read `PROTOCOL.md` — execution rules, commit protocol, failure handling
2. Read `../CLAUDE.md` — project structure, dev commands, gotchas
3. Pick a ticket folder — read its `AGENT.md` for context and `PROGRESS.md` for the next open subtask
4. Read the subtask file top to bottom, then read every file it will modify
5. Execute

---

## Directory Layout

```
tickets/
├── README.md               ← you are here
├── PROTOCOL.md             ← global agent execution rules (read once per session)
├── index.yaml              ← machine-readable ticket/subtask index (source of truth for status)
├── _templates/
│   ├── ticket.md           ← template for parent tickets
│   ├── subtask.md          ← template for subtask files
│   └── progress.md         ← template for progress tracking
├── NNN-short-name.md       ← parent ticket (summary + subtask index)
└── NNN-short-name/         ← subtask folder
    ├── AGENT.md            ← ticket-specific agent instructions
    ├── PROGRESS.md         ← subtask status tracker
    ├── decisions.md        ← non-obvious implementation choices
    └── ST-NNN-slug.md      ← individual subtask files
```

---

## Naming Conventions

| Item | Format | Example |
|---|---|---|
| Ticket | `NNN-kebab-case-name` | `006-fast-initial-load` |
| Subtask file | `ST-NNN-kebab-case-slug.md` | `ST-002-mode-aggregation.md` |
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
4. Create `NNN-short-name/PROGRESS.md` from `_templates/progress.md`
5. Create `NNN-short-name/AGENT.md` with ticket-specific agent instructions
6. Create `NNN-short-name/decisions.md` for implementation decisions
7. Add the ticket to `index.yaml`

All sections in the templates are required unless marked `(optional)`. If a section does not
apply, write "N/A" rather than deleting the heading — this keeps the structure scannable.
