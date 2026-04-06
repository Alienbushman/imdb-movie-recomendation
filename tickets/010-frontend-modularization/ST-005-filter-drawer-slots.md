---
id: ST-005
ticket: "010"
title: "Add Slots to FilterDrawer for Page-Specific Sections"
priority: Low
risk: low
status: Open
dependencies: []
subsystems: [frontend]
---

# ST-005 — Add Slots to FilterDrawer for Page-Specific Sections

**Priority:** Low
**Risk:** Low
**Files modified:** `frontend/app/components/FilterDrawer.vue`

## Problem

T009-ST4 needs to add a "Seen Status" toggle to the filter drawer, but only on the
`/similar` page. The current FilterDrawer has no extension point — the only way to add
page-specific content is to edit the component and add route-conditional blocks. This
means every page-specific filter addition requires modifying FilterDrawer.vue.

## Fix

Read `frontend/app/components/FilterDrawer.vue` before editing.

### Step 1 — Add a named slot inside the expansion panels

Add a `<slot name="extra-panels" />` inside the `v-expansion-panels` block, after the
last panel (Quality):

```html
<v-expansion-panels v-model="openPanels" multiple variant="accordion" flat>
  <!-- ... existing panels ... -->

  <!-- Extension point for page-specific filter panels -->
  <slot name="extra-panels" />
</v-expansion-panels>
```

This allows any page to inject additional `v-expansion-panel` elements into the
filter sidebar without modifying FilterDrawer.vue.

### Step 2 — Verify existing usage is unaffected

The slot has no default content, so existing pages that use `<FilterDrawer />`
without passing slot content see no change.

## Anti-patterns

- Do NOT add route-based conditionals inside FilterDrawer — the slot approach keeps
  the component page-agnostic
- Do NOT change any existing panel markup

## Post-conditions

```bash
grep -n 'slot name="extra-panels"' frontend/app/components/FilterDrawer.vue
# Expected: 1 match
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/components/FilterDrawer.vue
```

## Commit Message

```
refactor: add extra-panels slot to FilterDrawer for page-specific sections
```
