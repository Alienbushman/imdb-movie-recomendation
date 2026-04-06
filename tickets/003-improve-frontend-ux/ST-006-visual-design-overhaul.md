---
ticket: "003"
subtask: 6
title: "Visual Design Overhaul"
status: done
effort: medium-high
component: frontend
depends_on: [1, 5]
files_modified:
  - frontend/nuxt.config.ts
  - frontend/app/layouts/default.vue
  - frontend/app/pages/index.vue
  - frontend/app/components/RecommendationCard.vue
  - frontend/app/pages/dismissed.vue
files_created: []
---

# SUBTASK 06: Visual Design Overhaul

---

## Objective

Transform the site from default Vuetify dark theme into a polished, cinema-inspired design with custom colors, better typography, hover effects, loading states, and visual hierarchy.

## Context

The current site uses the stock Vuetify 4 dark theme with no customization (`nuxt.config.ts:8-13`):
```typescript
vuetify: {
  vuetifyOptions: {
    theme: {
      defaultTheme: 'dark',
    },
  },
},
```

This results in:
- Default grey background, default surface colors
- No brand identity or visual personality
- No card hover effects or transitions
- Loading state is a simple `v-progress-linear` or button `loading` prop
- No skeleton placeholders while content loads
- Flat visual hierarchy — everything is the same visual weight
- Empty state is just an icon and text

## Implementation

### 1. Custom Vuetify theme

Define a cinema-inspired dark theme in `nuxt.config.ts`:

```typescript
vuetify: {
  vuetifyOptions: {
    theme: {
      defaultTheme: 'dark',
      themes: {
        dark: {
          colors: {
            background: '#0a0a0f',       // Near-black with slight blue
            surface: '#14141f',           // Card background
            'surface-variant': '#1e1e2e', // Elevated surfaces
            primary: '#6366f1',           // Indigo accent (modern)
            secondary: '#a78bfa',         // Lighter purple
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6',
            success: '#22c55e',
            'on-background': '#e2e8f0',
            'on-surface': '#e2e8f0',
          },
        },
      },
    },
  },
},
```

The indigo/purple palette gives a premium "streaming service" feel while maintaining readability.

### 2. App bar enhancement

Update `layouts/default.vue`:
- Add a subtle gradient or border-bottom to the app bar
- Add an app icon/logo (e.g., `mdi-movie-open-star`)
- Improve the title typography

```vue
<v-app-bar color="surface" elevation="0" border="b">
  <template #prepend>
    <v-icon color="primary" size="28" class="ml-4">mdi-movie-open-star</v-icon>
  </template>
  <v-app-bar-title>
    <NuxtLink to="/" class="text-decoration-none text-on-surface font-weight-bold">
      IMDB Recommendations
    </NuxtLink>
  </v-app-bar-title>
  ...
</v-app-bar>
```

### 3. Card hover effects

Add subtle hover transitions to `RecommendationCard.vue`:

```css
.recommendation-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.recommendation-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
}
```

The predicted score chip should also subtly scale on card hover:
```css
.recommendation-card:hover .score-chip {
  transform: scale(1.1);
}
```

### 4. Loading skeleton placeholders

Replace the empty grid during loading with skeleton cards:

```vue
<v-row v-if="recommendations.loading && !recommendations.data">
  <v-col v-for="i in 8" :key="i" cols="12" sm="6" md="4" lg="3">
    <v-skeleton-loader type="card" />
  </v-col>
</v-row>
```

For subsequent loads (re-filtering), overlay a subtle loading indicator on the existing cards rather than replacing them.

### 5. Enhanced empty state

Replace the plain icon + text empty state with something more engaging:

```vue
<div class="text-center py-16">
  <v-icon size="80" color="primary" class="mb-6 opacity-50">mdi-movie-search</v-icon>
  <h2 class="text-h5 font-weight-bold mb-2">Discover Your Next Favorite</h2>
  <p class="text-body-1 text-medium-emphasis mb-6">
    Generate personalized recommendations based on your IMDB ratings
  </p>
  <v-btn color="primary" size="large" prepend-icon="mdi-play" @click="recommendations.generate(false)">
    Get Started
  </v-btn>
</div>
```

### 6. Score badge visual improvement

Make the predicted score more visually prominent on cards:

```vue
<v-chip
  :color="scoreColor(recommendation.predicted_score)"
  size="small"
  class="ml-2 font-weight-bold score-chip elevation-2"
  variant="flat"
>
  <v-icon size="x-small" start>mdi-star</v-icon>
  {{ recommendation.predicted_score.toFixed(1) }}
</v-chip>
```

### 7. Typography improvements

Add custom font weights and sizes:
- Card titles: `font-weight: 600`, slightly larger
- Section labels in filter panel: `text-overline` or `font-weight: 700`
- Explanation text: `text-body-2` with `text-medium-emphasis`
- Tab labels: slightly larger with better spacing

### 8. Smooth tab transitions

Add a fade transition when switching between Movies / Series / Animation tabs:

```vue
<v-window v-model="recommendations.tab">
  <v-window-item value="movies" transition="fade-transition">
    ...
  </v-window-item>
</v-window>
```

Or use Vue's `<transition>` component on the card grid with a stagger effect.

### 9. Subtle background pattern or gradient

Add a very subtle radial gradient to the page background to avoid the flat look:

```css
.v-application {
  background: radial-gradient(ellipse at top, #14141f 0%, #0a0a0f 70%) !important;
}
```

## Acceptance Criteria

- [x] Custom dark theme with cinema-inspired color palette is applied globally
- [x] App bar has visual polish (icon, improved title, subtle bottom border)
- [x] Cards have smooth hover effects (lift + shadow)
- [x] Loading skeleton placeholders appear while initial data loads
- [x] Empty state is visually engaging with a clear call-to-action
- [x] Score badges are visually prominent with star icon
- [x] Typography has clear visual hierarchy (headings, body, captions)
- [x] Tab transitions are smooth
- [x] Overall design feels cohesive and polished, not like a default Vuetify scaffold
- [x] All existing functionality works — no regressions

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
