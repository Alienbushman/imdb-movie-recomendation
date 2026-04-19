# Agent Instructions — Ticket 019

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for implementation.

---

## Goal

Make the **Seen Status** toggle on the Similar page actually re-fetch results when changed.
The fix is a single `watch` call in `FilterDrawer.vue`.

---

## Subtask Order

```
ST-001  ← wire seenFilter watcher (no deps)
```

---

## Ticket-Specific Context

### Why the watch is missing

`FilterDrawer.vue` is shared across three pages (recommendations, similar, person).
Its primary `watch` covers all `filters.*` reactive values and calls `scheduleApply()`
unconditionally. `similar.seenFilter` was never added to that watch — likely because
the Seen Status panel was added later as a similar-page-only feature, and the author
wired the UI but forgot the reactivity.

The `resetAndApply` function already resets `similar.seenFilter` and calls
`similar.applyFilters()`, confirming the intended pattern. The fix just applies the
same pattern for the change path.

### Why a separate watch (not merged into the existing one)

The existing watch fires on every page. Adding `similar.seenFilter` to it would cause
spurious `scheduleApply()` calls on the recommendations and person pages (where
`seenFilter` is irrelevant). A separate watcher that guards on `isSimilarPage.value`
keeps the pages independent.

### Lint and test commands

```bash
cd frontend && npx nuxt typecheck
uv run pytest tests/ -q   # no-op for this ticket (frontend only)
```
