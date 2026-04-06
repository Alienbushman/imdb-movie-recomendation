---
ticket: "003"
subtask: 1
title: "Redesign Filter Panel UX"
status: done
effort: medium
component: frontend
depends_on: []
files_modified:
  - frontend/app/pages/index.vue
  - frontend/app/stores/filters.ts
files_created: []
---

# SUBTASK 01: Redesign Filter Panel UX

---

## Objective

Replace the hidden slide-out filter drawer with an accessible, always-visible filter panel that groups related controls logically and supports searching within long option lists.

## Context

The current filter implementation has several UX problems:

- **Hidden by default:** Filters live in a `v-navigation-drawer` (`temporary`, `location="right"`) that users must discover and toggle via a "Filters" button. First-time users may not realize filters exist.
- **Manual apply:** All changes require clicking "Apply Filters" — there's no immediate feedback on what filters do.
- **Long unstructured lists:** Include Genres shows all 23 genres as a flat chip group. Exclude Genres duplicates the same 23 chips. Exclude Languages shows all 29 languages as chips. These are overwhelming to scan.
- **No search:** Users looking for a specific genre or language must visually scan the entire list.
- **No grouping:** Year range, genres, language, rating, and runtime are stacked vertically with only small subtitle text separating them.

### Current implementation
- Filter drawer: `index.vue:180-349`
- Filter state: `stores/filters.ts`
- 23 genres in `ALL_GENRES`, 29 languages in `ALL_LANGUAGES`, 37 countries in `ALL_COUNTRY_CODES`

## Implementation

### 1. Replace drawer with persistent sidebar or collapsible left panel

Replace the `v-navigation-drawer temporary` with a permanent left-side panel. Two layout options (pick the better fit):

**Option A — Persistent sidebar:** Use `v-navigation-drawer` with `permanent` on desktop, collapsible on mobile. The recommendations grid shifts to accommodate.

**Option B — Collapsible inline panel:** A `v-expansion-panels` section above the recommendation grid that starts expanded. Filters are visible but can be collapsed to maximize card space.

Recommendation: **Option A** for desktop (sidebar is standard for filter-heavy UIs like Netflix, shopping sites), falling back to a bottom sheet or modal on mobile (`< md` breakpoint).

### 2. Group filters into collapsible sections

Organize filters into logical `v-expansion-panel` groups within the sidebar:

1. **Content Type** — Per-category count controls (from subtask 02), title type toggles
2. **Date & Runtime** — Year range (from subtask 03), max runtime slider
3. **Genres** — Include and exclude in a single panel with a search field
4. **Language & Region** — Language filter, country filter, exclude languages
5. **Quality** — Min IMDB rating slider, min predicted score slider

Each section should default to collapsed except "Genres" and "Quality" (most frequently used).

### 3. Add search/filter within genre and language lists

Add a `v-text-field` with a search icon above each chip group that filters the displayed chips by substring match:

```vue
<v-text-field
  v-model="genreSearch"
  placeholder="Search genres..."
  density="compact"
  hide-details
  prepend-inner-icon="mdi-magnify"
  clearable
  class="mb-2"
/>
<v-chip-group ...>
  <v-chip
    v-for="genre in filteredGenres"
    ...
  />
</v-chip-group>
```

Where `filteredGenres = computed(() => ALL_GENRES.filter(g => g.toLowerCase().includes(genreSearch.value.toLowerCase())))`.

Same pattern for language exclusion chips.

### 4. Combine include/exclude genre selection

Instead of two separate 23-chip groups, use a single genre list where each chip has three states:
- **Neutral** (unselected): genre is not filtered
- **Include** (primary color): genre is included
- **Exclude** (error color): genre is excluded

Clicking a neutral chip includes it. Clicking an included chip toggles it to excluded. Clicking an excluded chip resets it to neutral. This halves the visual clutter.

Alternatively, use a simpler two-row approach: one `v-chip-group` for include, one for exclude, but both in the same `v-expansion-panel` with clear labels and the search field filtering both simultaneously.

### 5. Active filter summary bar

Keep the existing active filter summary chips at the top of the recommendations area (already implemented at `index.vue:73-110`). Ensure each chip is closable and immediately removes that filter.

### 6. Responsive behavior

- **Desktop (≥ 960px):** Persistent sidebar, ~300px wide
- **Tablet (600–959px):** Collapsible sidebar, toggled by button
- **Mobile (< 600px):** Bottom sheet or full-screen dialog for filters

## Acceptance Criteria

- [x] Filters are visible without user action on desktop (not hidden in a drawer)
- [x] Filters are grouped into collapsible sections with clear labels
- [x] Genre and language lists have a search/filter text field
- [x] Include and exclude genres are combined into a single, less cluttered interface
- [x] Active filter summary chips remain visible at the top of the recommendations grid
- [x] Responsive: sidebar on desktop, collapsible or bottom sheet on mobile
- [x] No functionality lost — all existing filter options remain available

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
