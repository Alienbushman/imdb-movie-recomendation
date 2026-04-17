# Agent Instructions — Ticket 017

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for implementation.

---

## Goal

Add two navigation affordances to the `RecommendationCard` detail dialog:

1. A **Find Similar** button that deep-links to `/similar` seeded with the card's title.
2. Clickable director and actor chips that deep-link to `/person` for the selected person.

Both targets must accept their state via URL query params so page reloads work.

---

## Subtask Order

```
ST-001  ← similar page deep-link support (no deps)
ST-002  ← person page deep-link support (no deps, parallel with ST-001)
ST-003  ← Find Similar button in card popup (depends on ST-001)
ST-004  ← clickable person chips in card popup (depends on ST-002)
```

ST-001 and ST-002 can run in any order. ST-003 should not land before ST-001 is in,
and ST-004 should not land before ST-002 is in — otherwise the navigation would land
on a page that doesn't yet understand the query params.

---

## Ticket-Specific Context

### Why no backend changes are needed

The pipeline populates the `people` table using `name_id = name.lower()`
(see [pipeline.py:166](../../app/services/pipeline.py#L166)). This means the
frontend can compute a valid `name_id` from any actor/director display name on a
scored card without a server round-trip. The `/people/{name_id:path}` endpoint
already accepts paths with spaces (encoded as `%20`), and the `name` field in the
response is the authoritative display name — so a minimal
`PersonSearchResult` object can be constructed from just the name string.

For the similar page, all fields displayed in the search bar selection
(`title`, `year`, `title_type`) are already on the card. The store's
`fetchSimilar()` only reads `selectedSeed.imdb_id`, so a minimal
`TitleSearchResult` built from the card's data is enough to bootstrap results.

### Store bootstrap pattern

Each store needs a small helper that sets the `selectedSeed` / `selectedPerson`
from a plain object and immediately triggers the fetch. Example for similar:

```ts
async function selectSeedById(seed: TitleSearchResult) {
  selectedSeed.value = seed
  await fetchSimilar()
}
```

The page's `onMounted` hook reads `useRoute().query` and, when the required keys
are present and there is no current selection, calls the helper. Use a guard so
that subsequent route changes (e.g. navigating away and back) don't reset
state unexpectedly.

### Router navigation pattern

Inside the card component use Nuxt's `navigateTo` helper:

```ts
async function openPerson(name: string) {
  await navigateTo({
    path: '/person',
    query: { name_id: name.toLowerCase(), name },
  })
}
```

Wrap the chip click with `.stop` so it does not toggle the dialog backdrop.
Closing the dialog explicitly before navigating is not required — the page
transition unmounts the component and the dialog closes naturally.

### Lint and test commands

```bash
cd frontend && npx nuxt typecheck
uv run ruff check app/        # will be a no-op for this ticket (frontend only)
uv run pytest tests/ -q
```
