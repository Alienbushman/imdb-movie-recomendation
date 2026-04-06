# TICKET-006 Decisions

_Record non-obvious implementation choices here as subtasks are completed._

## ST-001 — Package choice

The subtask specified `@pinia-plugin-persistedstate/nuxt`, but that package's latest version (1.2.1) has a peer dependency on `@pinia/nuxt@^0.5.0` (i.e. `>=0.5.0 <0.6.0`), which conflicts with our `@pinia/nuxt@0.11.3`.

Used `pinia-plugin-persistedstate@4.7.1` instead — the main package now ships its own Nuxt module at `pinia-plugin-persistedstate/nuxt` and requires `@pinia/nuxt@>=0.10.0`. Functionally identical; the `persist` option in `defineStore` works the same way.

## ST-001 — sortBy persistence consolidation

A linter hook migrated the manual `localStorage.getItem/setItem` for `sortBy` (from ticket 008) to use the new persistence plugin, adding `'sortBy'` to the `persist.pick` array. This is correct — one persistence mechanism is better than two.
