---
ticket: "003"
subtask: 5
title: "Fix Card Layout, Spacing, and Show Region"
status: done
effort: low-medium
component: frontend
depends_on: []
files_modified:
  - frontend/app/components/RecommendationCard.vue
  - frontend/app/pages/index.vue
files_created: []
---

# SUBTASK 05: Fix Card Layout, Spacing, and Show Region

---

## Objective

Fix inconsistent card heights and spacing in the recommendation grid, and add country/region display to each card so users can see where a movie or series is from.

## Context

### Card layout issues
The current grid (`index.vue:154-177`) uses `v-col cols="12" sm="6" md="4" lg="3"` with `align="stretch"` on the row. Cards use `height="100%"` and `d-flex flex-column`. However:

- **Inconsistent content height:** Cards with long explanation lists, many genres, or multiple actors are much taller than minimal cards. The `align="stretch"` makes all cards in a row match the tallest, but across rows the heights vary wildly, creating an uneven visual rhythm.
- **Genre chip overflow:** Cards with many genres (e.g., "Action, Adventure, Animation, Comedy, Fantasy, Sci-Fi") create 2-3 lines of chips, pushing everything down.
- **Explanation list unbounded:** The `v-list` of explanations can have up to 5 items, each a full sentence.
- **No gap control:** The grid relies on Vuetify's default column padding. There's no explicit gap between cards.

### Region not displayed
`Recommendation` has `country_code: string | null` from the backend, but `RecommendationCard.vue` never renders it. Users want to see the region/country at a glance.

The `country_code` is an ISO 3166-1 alpha-2 code (e.g., "US", "KR", "FR"). The `ALL_COUNTRY_CODES` array in `stores/filters.ts` has the mapping from codes to display names.

## Implementation

### 1. Add region/country display to cards

Show the country next to the year and title type in the subtitle area:

```vue
<v-card-subtitle class="d-flex align-center ga-2 flex-wrap">
  <span v-if="recommendation.year">{{ recommendation.year }}</span>
  <v-chip size="x-small" label>{{ recommendation.title_type }}</v-chip>
  <v-chip v-if="recommendation.country_code" size="x-small" variant="tonal" prepend-icon="mdi-map-marker">
    {{ countryName }}
  </v-chip>
  <span v-if="recommendation.imdb_rating" class="text-caption">
    IMDB {{ recommendation.imdb_rating }}
  </span>
</v-card-subtitle>
```

Resolve country code to name using a utility function or import from the filters store:

```typescript
const countryName = computed(() => {
  if (!props.recommendation.country_code) return null
  const entry = ALL_COUNTRY_CODES.find(c => c.code === props.recommendation.country_code)
  return entry ? entry.name : props.recommendation.country_code
})
```

Alternatively, use a flag emoji or a short label like "US", "KR" to save space. If the country is common (US, GB), showing just the code may be cleaner than the full name.

### 2. Cap card height and add content truncation

Set a consistent max height on cards and truncate overflowing content:

**Genre chips:** Limit to 3-4 visible genres, show a "+N more" chip for the rest:
```vue
<v-chip v-for="genre in recommendation.genres.slice(0, 4)" ...>{{ genre }}</v-chip>
<v-chip v-if="recommendation.genres.length > 4" size="x-small" variant="text">
  +{{ recommendation.genres.length - 4 }}
</v-chip>
```

**Explanation list:** Limit to 2-3 items visible, with a "show more" expand:
```vue
<v-list-item
  v-for="(reason, i) in visibleExplanations"
  :key="i"
  ...
/>
<v-btn v-if="recommendation.explanation.length > 3" size="x-small" variant="text" @click="showAllExplanations = !showAllExplanations">
  {{ showAllExplanations ? 'Show less' : `+${recommendation.explanation.length - 3} more` }}
</v-btn>
```

**Actors:** Already limited to 3 by the backend. Keep as-is.

**Similar titles:** Already limited to 3. Consider using a single line with overflow ellipsis.

### 3. Improve grid spacing

Add explicit gap between cards and adjust column sizing:

```vue
<v-row data-e2e="recommendations-grid" :dense="false" class="ga-4">
  <v-col
    v-for="rec in recommendations.currentList"
    :key="rec.imdb_id ?? rec.title"
    cols="12"
    sm="6"
    md="4"
    lg="3"
    xl="2"
    class="d-flex"
  >
```

The `ga-4` class adds a consistent 16px gap. Adding `xl="2"` allows 6 cards per row on ultrawide displays.

### 4. Consider fixed card height with scroll

An alternative approach for truly uniform cards:

```css
.recommendation-card {
  max-height: 420px;
  overflow-y: auto;
}
```

This is less ideal than content truncation but simpler. Use truncation (step 2) as the primary approach, with a max-height as a safety net.

### 5. Improve card padding

Add consistent internal padding:

```css
.v-card-text {
  padding-top: 8px;
  padding-bottom: 8px;
}
```

Ensure the dismiss button area has consistent spacing from the content above it.

## Acceptance Criteria

- [x] Country/region is displayed on each card (using country code or resolved name)
- [x] Genre chips are capped at 4 visible, with "+N" overflow indicator
- [x] Explanation list is capped at 3 visible, with expand/collapse toggle
- [x] Cards have consistent visual height within a row and across rows
- [x] Grid has explicit, consistent gaps between cards
- [x] Cards remain fully functional (dismiss, genre exclude, language exclude still work)
- [x] Responsive grid still works correctly at all breakpoints
- [x] `xl` breakpoint added for ultrawide displays (6 cards per row)

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
