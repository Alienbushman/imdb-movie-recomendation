---
id: ST-004
ticket: "017"
title: "Clickable director/actor chips in card popup"
priority: Medium
risk: low
status: Done
dependencies: [ST-002]
subsystems: [frontend]
---

# ST-004 — Clickable Director/Actor Chips in Card Popup

**Priority:** Medium
**Risk:** Low
**Files:** `frontend/app/components/RecommendationCard.vue`

## Problem

Today the card detail dialog renders the director and cast as plain joined
text:

```vue
<!-- Director -->
<div v-if="item.director" class="mb-3">
  <div class="text-overline text-medium-emphasis mb-1">Director</div>
  <div class="text-body-1">
    <v-icon size="small" class="mr-1">mdi-movie-open</v-icon>
    {{ item.director }}
  </div>
</div>

<!-- Actors -->
<div v-if="item.actors.length" class="mb-3">
  <div class="text-overline text-medium-emphasis mb-1">Cast</div>
  <div class="text-body-1">
    <v-icon size="small" class="mr-1">mdi-account-group</v-icon>
    {{ item.actors.join(', ') }}
  </div>
</div>
```

These should become individually clickable chips that deep-link to the person
page introduced by ST-002. Per
[pipeline.py:166](../../app/services/pipeline.py#L166), `name_id = name.toLowerCase()`
on the backend, so no API call is needed to resolve the navigation target.

## Pre-conditions

```bash
# Confirm the current plain-text markup is still there
grep -n "item.actors.join" frontend/app/components/RecommendationCard.vue
# Expected: 2 matches — one in the compact card face, one in the dialog.
# Only the DIALOG instance changes in this subtask.
```

```bash
# Verify ST-002 has landed — the person page must understand the query params
grep -n "selectPersonById" frontend/app/stores/person.ts
# Expected: at least 2 matches (definition + return statement)
```

If the ST-002 check fails, stop and complete ST-002 first.

## Fix

### Step 1 — Add a navigation handler in the script block

Add a single handler that works for both directors and actors:

```ts
async function openPerson(name: string) {
  if (!name) return
  dialogOpen.value = false
  await navigateTo({
    path: '/person',
    query: {
      name_id: name.toLowerCase(),
      name,
    },
  })
}
```

`navigateTo` is a Nuxt auto-import.

### Step 2 — Replace the Director block in the dialog

In the `<v-dialog>` / `<v-card-text>` section of the template, find the
Director block (shown above) and replace the inner `<div class="text-body-1">`
with a single clickable chip:

```vue
<!-- Director -->
<div v-if="item.director" class="mb-3">
  <div class="text-overline text-medium-emphasis mb-1">Director</div>
  <v-chip
    data-e2e="dialog-director-chip"
    size="small"
    variant="tonal"
    color="primary"
    prepend-icon="mdi-movie-open"
    class="chip-clickable"
    @click="openPerson(item.director!)"
  >
    {{ item.director }}
  </v-chip>
</div>
```

The non-null assertion (`item.director!`) is safe because the outer `v-if`
already guards on `item.director`.

### Step 3 — Replace the Cast block in the dialog

Replace the Cast block with a wrap of individual chips — one per actor:

```vue
<!-- Actors -->
<div v-if="item.actors.length" class="mb-3">
  <div class="text-overline text-medium-emphasis mb-1">Cast</div>
  <div class="d-flex flex-wrap ga-1">
    <v-chip
      v-for="actor in item.actors"
      :key="actor"
      data-e2e="dialog-actor-chip"
      size="small"
      variant="tonal"
      color="primary"
      prepend-icon="mdi-account"
      class="chip-clickable"
      @click="openPerson(actor)"
    >
      {{ actor }}
    </v-chip>
  </div>
</div>
```

### Step 4 — Add a small cursor/hover style for the new chips

In the scoped `<style>` block at the bottom of the file, add:

```css
.chip-clickable {
  cursor: pointer;
}
```

The existing `.chip-exclude:hover` rule is scoped to genre chips and does not
apply here.

## Anti-patterns

- Do NOT change the compact card face (the `<v-card-title>` / `<v-card-text>`
  **outside** the `<v-dialog>`). Scope is the dialog only — the compact face
  keeps the joined-text form to preserve the one-line density.
- Do NOT compute `name_id` in any way other than `name.toLowerCase()`. That is
  the exact transformation the backend pipeline uses to populate the `people`
  table; any other normalisation (trim, diacritic fold, etc.) will produce a
  404.
- Do NOT conditionally hide chips based on `name_id` length or content —
  if the backend stored it, the frontend should route to it. Broken routing
  will surface as a 404 in the person page, which is the correct failure mode.
- Do NOT add an `@click.stop` modifier — the chips live inside the dialog,
  which is already a separate event scope from the card body.

## Post-conditions

```bash
grep -n "openPerson" frontend/app/components/RecommendationCard.vue
# Expected: at least 3 matches (definition + director click + actor click)
```

```bash
grep -n "dialog-actor-chip" frontend/app/components/RecommendationCard.vue
# Expected: 1 match
```

```bash
grep -n "dialog-director-chip" frontend/app/components/RecommendationCard.vue
# Expected: 1 match
```

```bash
# Confirm the dialog no longer joins actors as plain text
grep -c "item.actors.join" frontend/app/components/RecommendationCard.vue
# Expected: 1 (only the compact card face retains the joined form)
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

Manual smoke test: open a card, click any actor or director chip, verify the
person page loads that person's titles and the URL reflects
`?name_id=...&name=...`. Reload the browser on the resulting URL and verify
the titles reload correctly.

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
feat: clickable director/actor chips in card popup (ST-004)
```

## Gotchas

- The popup uses `prepend-icon` on the chip; the icon name for actors is
  `mdi-account` (single), distinct from the compact card's `mdi-account-group`
  which sits next to the joined name list. Do not reuse `mdi-account-group`
  inside each per-actor chip — it implies a plurality that is wrong at chip scale.
- `item.actors` may be an empty array on `toPersonCardItem` results (the person
  page currently constructs cards without per-title actor data). The outer
  `v-if="item.actors.length"` correctly hides the Cast block in that case.
