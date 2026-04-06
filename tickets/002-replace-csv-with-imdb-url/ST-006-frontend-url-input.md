---
ticket: "002"
subtask: 6
title: "Frontend: Add IMDB URL Input to UI"
status: open
effort: low
component: frontend
depends_on: [5]
files_modified:
  - frontend/app/pages/index.vue
files_created: []
---

# SUBTASK 06: Frontend — Add IMDB URL Input to UI

---

## Objective

Add an IMDB ratings URL text input to the main page UI. Wire it to the `generate()` function so the URL is passed to the API when recommendations are triggered.

## Context

Read `frontend/app/pages/index.vue` before making changes to understand:
- Where the existing action buttons (generate/retrain) are positioned
- The reactive state management pattern used (`ref`, `computed`)
- The Vuetify component conventions already in use
- Where `generate()` is defined and how it calls `api.getRecommendations()`

The UI uses Nuxt 4 + Vuetify 4. Use Vuetify's `v-text-field` component to match the existing style.

## Implementation

### 1. Add reactive state

In the `<script setup>` section, add:

```typescript
const imdbUrl = ref<string>('')
```

### 2. Add URL input to template

Place a `v-text-field` above (or near) the generate button:

```vue
<v-text-field
  v-model="imdbUrl"
  label="IMDB Ratings URL"
  placeholder="https://www.imdb.com/user/ur.../ratings/"
  hint="Your IMDB ratings must be set to public"
  persistent-hint
  clearable
  variant="outlined"
  prepend-inner-icon="mdi-link"
/>
```

Adjust `variant` and other props to match the existing component style in the page.

### 3. Wire URL into `generate()`

Update the `generate()` call to pass `imdbUrl.value`:

```typescript
async function generate(retrain = false) {
  // ... existing logic
  await api.getRecommendations(buildFilters(), retrain, imdbUrl.value || undefined)
  // ...
}
```

Pass `undefined` (not empty string) when the field is empty so the backend doesn't receive an empty `imdb_url` query param.

### 4. Keep existing auto-generate on mount

The `onMounted(() => generate())` call should remain. When no URL is set, it falls back to the server-side CSV as before.

### 5. Error display

The existing error display mechanism (however the page currently shows API errors) should surface the new error messages from the backend (invalid URL, private ratings, IMDB unreachable) without additional changes — the error propagates through the existing response/error handling.

## Acceptance Criteria

- [ ] `v-text-field` visible on the main page for IMDB URL input
- [ ] Entering a URL and clicking generate sends it to the API
- [ ] Empty URL field → `imdb_url` param omitted from request (fallback to local CSV)
- [ ] Clearable button resets the URL field
- [ ] Hint text "Your IMDB ratings must be set to public" visible below the field
- [ ] Component style matches the existing UI conventions
- [ ] `onMounted` auto-generate still works when URL field is empty

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
