---
id: ST-002
ticket: "008"
title: "Scroll-to-Top FAB"
priority: Low
risk: zero
status: Done
dependencies: []
subsystems: [frontend]
---

# ST-002 — Scroll-to-Top FAB

**Priority:** Low
**Risk:** Zero
**Files:** `frontend/app/pages/index.vue`

## Problem

The card grid can be 20-30+ cards tall. Once a user scrolls down, they have to scroll all the
way back up to reach the filter sidebar, tabs, or action buttons. There is no scroll-to-top
affordance.

## Pre-conditions

```bash
# Confirm the main content div exists with overflow-auto
grep -n "overflow-auto" frontend/app/pages/index.vue
# Expected: at least 1 match

# Confirm onMounted is imported
grep -n "onMounted" frontend/app/pages/index.vue
# Expected: at least 1 match
```

## Fix

Read `frontend/app/pages/index.vue` before editing to confirm the current state.

### Step 1 — Add ref to main content div

Add `ref="contentArea"` to the main content `div`:

```html
<div ref="contentArea" class="flex-grow-1 pa-4 overflow-auto">
```

### Step 2 — Add script logic

```ts
const contentEl = useTemplateRef<HTMLElement>('contentArea')
const showScrollTop = ref(false)

function onScroll() {
  showScrollTop.value = (contentEl.value?.scrollTop ?? 0) > 300
}

function scrollToTop() {
  contentEl.value?.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => contentEl.value?.addEventListener('scroll', onScroll))
onUnmounted(() => contentEl.value?.removeEventListener('scroll', onScroll))
```

### Step 3 — Add button to template

Add inside the main content div, after the card grid:

```html
<v-btn
  v-if="showScrollTop"
  icon="mdi-chevron-double-up"
  color="primary"
  variant="tonal"
  size="small"
  style="position: fixed; bottom: 24px; right: 24px; z-index: 10"
  @click="scrollToTop"
/>
```

## Anti-patterns

- Do NOT use `window.scrollTo` — the scrollable element is the content div, not the window
- Do NOT forget `onUnmounted` cleanup — leaking scroll listeners causes memory issues
- Do NOT position the button where it overlaps the filter sidebar

## Post-conditions

```bash
# Confirm scroll-to-top button exists
grep -n "scrollToTop" frontend/app/pages/index.vue
# Expected: at least 2 matches (function + @click)

# Confirm contentArea ref exists
grep -n "contentArea" frontend/app/pages/index.vue
# Expected: at least 2 matches (ref attribute + useTemplateRef)
```

## Tests

```bash
# Frontend types
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/pages/index.vue
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
feat: add scroll-to-top FAB on recommendation grid
```
