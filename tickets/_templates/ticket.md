---
id: "NNN"
title: "Ticket Title"
status: open
priority: high         # high | medium | low
component: backend     # backend | frontend | full_stack
files_affected:
  - path/to/file.py
---

# TICKET-NNN: Ticket Title

---

## Summary

One paragraph: what is this ticket about and why does it exist.

## Priority Breakdown

| Priority | Count |
|---|---|
| High | 0 |
| Medium | 0 |
| Low | 0 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](NNN-ticket-slug/ST-001-slug.md) | Short title | High | Open |

## Context

<!-- Background information an agent needs to understand before starting.
     Link to relevant docs, prior tickets, or external references. -->

## Files in Scope

<!-- List the files this ticket's subtasks will touch. Helps agents assess blast radius. -->

- `app/services/example.py`

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Scope Fence

- Only modify files listed in each subtask's "Files Changed" section
- Do not refactor surrounding code, even if it looks wrong
- Do not update dependencies or configuration beyond what the subtask requires
