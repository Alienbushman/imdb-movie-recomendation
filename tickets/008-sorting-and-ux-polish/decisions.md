# TICKET-008 Decisions Log

Record non-obvious implementation choices here as subtasks are completed. Future agents need to understand *why* the code is shaped a certain way — not just what changed.

## Format

```
### [ST-NNN — Title] Short description of the decision
**Context:** What was unclear or had multiple valid options.
**Decision:** What was chosen.
**Reason:** Why this option over the alternatives.
```

## Decisions

### [ST-001] Sort persistence uses pinia-plugin-persistedstate instead of manual localStorage
**Context:** Ticket specified `@pinia-plugin-persistedstate/nuxt` but it had a peer dep conflict with `@pinia/nuxt@0.11.3`. Meanwhile, ticket 006 work added persistedstate to the store externally.
**Decision:** Used the store's existing `persist.pick` array instead of manual localStorage watchers.
**Reason:** Cleaner than a parallel localStorage mechanism; consistent with how `pipelineReady` and `lastOperation` are already persisted.

### [ST-003] Grid density uses localStorage directly, not pinia persist
**Context:** Density is a single boolean UI preference, not store state.
**Decision:** Used `ref` + `watch` + `localStorage` in the page component.
**Reason:** Per the subtask spec — a simple boolean preference doesn't warrant store persistence. Keeps the concern local to the page.

### [ST-003] Switched from fixed column count to auto-fill minmax grid
**Context:** Original CSS used `repeat(2, 1fr)` with a `@media` breakpoint for 3 columns.
**Decision:** Replaced with `repeat(auto-fill, minmax(360px, 1fr))` (normal) / `minmax(280px, 1fr)` (dense).
**Reason:** Auto-fill adapts to all screen widths automatically, eliminating the need for manual breakpoints.
