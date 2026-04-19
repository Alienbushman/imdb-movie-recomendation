---
id: ST-003
ticket: "017"
title: "Find Similar button in card popup"
priority: Medium
risk: low
status: Done
dependencies: [ST-001]
subsystems: [frontend]
---

# ST-003 — Find Similar Button in Card Popup

**Priority:** Medium
**Risk:** Low
**Files:** `frontend/app/components/RecommendationCard.vue`

## Problem

The card detail dialog's action row (currently **View on IMDB** and **Dismiss**)
does not let users jump from a recommended title to titles similar to it.
Users have to copy the title, open the Find Similar page, type it back in, and
pick it from the autocomplete — a clunky, three-step detour.

Add a **Find Similar** button that deep-links to `/similar` using the new
query-param entry point introduced in ST-001.

## Pre-conditions

```bash
# Verify the action row structure is still as expected
grep -n "View on IMDB" frontend/app/components/RecommendationCard.vue
# Expected: 1 match inside the <v-dialog> block
```

```bash
# Verify ST-001 has landed — the similar page must understand the query params
grep -n "selectSeedById" frontend/app/stores/similar.ts
# Expected: at least 2 matches (definition + return statement)
```

If the ST-001 check fails, stop and complete ST-001 first.

## Fix

### Step 1 — Add a click handler in the script block

In [RecommendationCard.vue](../../frontend/app/components/RecommendationCard.vue),
add a handler in the `<script setup>` block. It must early-return when the
card has no `imdb_id` (e.g. an anonymous rated title without a resolved IMDB ID):

```ts
async function openFindSimilar() {
  if (!props.item.imdb_id) return
  dialogOpen.value = false
  await navigateTo({
    path: '/similar',
    query: {
      imdb_id: props.item.imdb_id,
      title: props.item.title,
      year: props.item.year ?? undefined,
      title_type: props.item.title_type,
    },
  })
}
```

`navigateTo` is a Nuxt auto-import — no explicit import needed.

### Step 2 — Add the button to the dialog action row

In the `<v-card-actions>` block inside the dialog (currently containing the
**View on IMDB** button and the **Dismiss** button), insert a new button
between them. Hide the button when `item.imdb_id` is falsy:

```vue
<v-btn
  v-if="item.imdb_id"
  data-e2e="btn-find-similar"
  variant="tonal"
  color="secondary"
  prepend-icon="mdi-movie-search"
  class="ml-2"
  @click="openFindSimilar"
>
  Find Similar
</v-btn>
```

Place it immediately after the **View on IMDB** `<v-btn>` and before the
`<v-spacer />` so the layout becomes: `[View on IMDB] [Find Similar] <spacer> [Dismiss]`.

## Anti-patterns

- Do NOT add the button to the compact card face (outside the dialog). The
  acceptance criteria only ask for it inside the popup.
- Do NOT pass undefined/null query values as empty strings — `navigateTo`
  handles `undefined` correctly and will omit the key. Passing `""` would
  round-trip through URL decoding and land as an empty string in the target
  page's query handler, breaking the ST-001 type guard.
- Do NOT forget the `v-if="item.imdb_id"` guard — the Find Similar page requires
  an imdb_id and rendering the button without one would produce a dead link.

## Post-conditions

```bash
grep -n "btn-find-similar" frontend/app/components/RecommendationCard.vue
# Expected: 1 match
```

```bash
grep -n "openFindSimilar" frontend/app/components/RecommendationCard.vue
# Expected: at least 2 matches (definition + handler binding)
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

Manual smoke test: run the frontend, generate recommendations, click a card,
click **Find Similar**, verify the similar page loads populated with results
for that seed and the URL reflects the query params.

## Files Changed

```
frontend/app/components/RecommendationCard.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: add Find Similar button to card popup (ST-003)
```

## Gotchas

- The dialog closes explicitly via `dialogOpen.value = false` before calling
  `navigateTo`. Skipping this is fine in practice (the page unmount closes it)
  but leaving it closed before the route transition makes the visual handoff
  smoother and avoids a brief flash of the old dialog on the new page.
