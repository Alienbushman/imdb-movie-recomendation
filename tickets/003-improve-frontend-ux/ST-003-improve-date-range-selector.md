---
ticket: "003"
subtask: 3
title: "Improve Date Range Selector"
status: done
effort: low
component: frontend
depends_on: [1]
files_modified:
  - frontend/app/pages/index.vue
  - frontend/app/stores/filters.ts
files_created: []
---

# SUBTASK 03: Improve Date Range Selector

---

## Objective

Replace the raw number input fields for year range with an intuitive dual-thumb range slider plus decade preset buttons, so users can quickly select a time period.

## Context

The current date range UI consists of two `v-text-field type="number"` fields labeled "From" and "To" (`index.vue:192-215`). This has several problems:

- **No visual feedback** — Users can't see at a glance what range they've selected
- **No presets** — Selecting "movies from the 90s" requires typing 1990 and 1999
- **No bounds guidance** — The fields accept any number with no indication of the valid range (1970–2026)
- **Error-prone** — Users might type "90" instead of "1990", or set min > max

The `config.yaml` minimum year is 1970, and the current year is 2026. These should bound the slider.

## Implementation

### 1. Dual-thumb range slider

Replace the two text fields with a Vuetify `v-range-slider`:

```vue
<p class="text-subtitle-2 mb-1">
  Year Range: {{ yearRange[0] }} – {{ yearRange[1] }}
</p>
<v-range-slider
  v-model="yearRange"
  :min="1970"
  :max="currentYear"
  :step="1"
  thumb-label="always"
  hide-details
/>
```

In the filters store, replace `minYear` and `maxYear` with a computed that reads/writes a `[min, max]` tuple. Alternatively, keep the two refs but bind them via a computed `yearRange`:

```typescript
const yearRange = computed({
  get: () => [minYear.value ?? 1970, maxYear.value ?? new Date().getFullYear()],
  set: (val: [number, number]) => {
    minYear.value = val[0] === 1970 ? undefined : val[0]
    maxYear.value = val[1] === new Date().getFullYear() ? undefined : val[1]
  },
})
```

This way moving the slider to the full range clears the filter (no unnecessary filtering).

### 2. Decade preset chips

Add quick-select buttons below (or above) the slider:

```vue
<div class="d-flex ga-1 flex-wrap mt-1">
  <v-chip
    v-for="preset in yearPresets"
    :key="preset.label"
    size="x-small"
    variant="outlined"
    @click="applyYearPreset(preset)"
  >
    {{ preset.label }}
  </v-chip>
</div>
```

Presets:
```typescript
const yearPresets = [
  { label: 'Last 5 years', min: currentYear - 5, max: currentYear },
  { label: '2020s', min: 2020, max: 2029 },
  { label: '2010s', min: 2010, max: 2019 },
  { label: '2000s', min: 2000, max: 2009 },
  { label: '90s', min: 1990, max: 1999 },
  { label: '80s', min: 1980, max: 1989 },
  { label: 'Classic', min: 1970, max: 1979 },
  { label: 'All', min: 1970, max: currentYear },
]
```

Clicking a preset sets both slider thumbs. Clicking "All" clears the year filter.

### 3. Validation

- Ensure min can't exceed max (the `v-range-slider` handles this natively)
- Display the selected range in text above the slider for clarity
- If both thumbs are at the extremes (1970 and current year), treat as "no filter"

## Acceptance Criteria

- [x] Year range uses a dual-thumb `v-range-slider` instead of two text inputs
- [x] Current selected range is displayed as text (e.g., "1990 – 2010")
- [x] Decade preset chips are available for quick selection
- [x] "All" or full-range resets the year filter to undefined
- [x] Slider bounds are 1970 (config minimum) to current year
- [x] Thumb labels show the year while dragging
- [x] No regression in filter functionality — year filter still works with API

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
